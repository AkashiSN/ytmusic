"""ADB sync: transfer media files to Android SD card."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)

MEDIA_EXTENSIONS = frozenset((
    ".opus", ".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aac", ".wma", ".m3u8",
))


def _is_media_file(path: str) -> bool:
    """Check if path has a recognized media file extension."""
    return Path(path).suffix.lower() in MEDIA_EXTENSIONS


def list_adb_devices(adb: str = "adb") -> list[str]:
    """Return list of connected ADB device serial numbers."""
    result = subprocess.run(
        [adb, "devices"], capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"adb devices failed: {result.stderr.strip()}")
    serials: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def detect_sd_cards(serial: str, adb: str = "adb") -> list[str]:
    """Detect SD card paths on device (e.g. /storage/XXXX-XXXX)."""
    result = subprocess.run(
        [adb, "-s", serial, "shell", "ls", "/storage/"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to list /storage/: {result.stderr.strip()}")
    sd_pattern = re.compile(r"^[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}$")
    cards: list[str] = []
    for entry in result.stdout.split():
        if sd_pattern.match(entry):
            cards.append(f"/storage/{entry}")
    return cards


def interactive_select(label: str, items: list[str]) -> str:
    """Prompt user to select from a list. Returns selected item."""
    print(f"\n{label}:")
    for i, item in enumerate(items, 1):
        print(f"  {i}) {item}")
    while True:
        try:
            choice = int(input("Select [1]: ").strip() or "1")
            if 1 <= choice <= len(items):
                return items[choice - 1]
        except (ValueError, EOFError):
            pass
        print(f"Please enter 1-{len(items)}")


def _resolve_device(serial: str | None, adb: str) -> str:
    """Resolve device serial: use provided, auto-select single, or prompt."""
    if serial:
        return serial
    devices = list_adb_devices(adb)
    if not devices:
        print("Error: No ADB devices connected", file=sys.stderr)
        sys.exit(1)
    if len(devices) == 1:
        logger.info("Using device: %s", devices[0])
        return devices[0]
    return interactive_select("Connected devices", devices)


def _resolve_sd_card(sd_card: str | None, serial: str, adb: str) -> str:
    """Resolve SD card path: use provided, auto-select single, or prompt."""
    if sd_card:
        return sd_card
    cards = detect_sd_cards(serial, adb)
    if not cards:
        print("Error: No SD card detected on device", file=sys.stderr)
        sys.exit(1)
    if len(cards) == 1:
        logger.info("Using SD card: %s", cards[0])
        return cards[0]
    return interactive_select("SD cards", cards)


def _parse_stat_line(line: str, prefix: str) -> tuple[str, int] | None:
    """Parse a single 'stat -c %s %n' output line.

    Returns (relative_path, size) if the line is valid and under prefix,
    or None otherwise.
    """
    line = line.strip()
    if not line:
        return None
    parts = line.split(" ", 1)
    if len(parts) != 2:
        return None
    try:
        size = int(parts[0])
    except ValueError:
        return None
    path = parts[1]
    if not path.startswith(prefix):
        return None
    rel = path[len(prefix):]
    if not _is_media_file(rel):
        return None
    return rel, size


def _collect_with_stat(
    serial: str, remote_dir: str, prefix: str, adb: str,
) -> dict[str, int] | None:
    """Try to collect remote files with sizes via stat.

    Returns file dict on success, or None if stat is unavailable.
    """
    result = subprocess.run(
        [adb, "-s", serial, "shell",
         f"find {remote_dir} -type f -exec stat -c '%s %n' {{}} +"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    files: dict[str, int] = {}
    for line in result.stdout.splitlines():
        parsed = _parse_stat_line(line, prefix)
        if parsed:
            rel, size = parsed
            files[rel] = size
    return files


def _collect_paths_only(
    serial: str, remote_dir: str, prefix: str, adb: str,
) -> dict[str, int]:
    """Collect remote file paths without sizes (fallback).

    Returns dict with all sizes set to -1 (unknown).
    """
    result = subprocess.run(
        [adb, "-s", serial, "shell", "find", remote_dir, "-type", "f"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {}
    files: dict[str, int] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            rel = line[len(prefix):]
            if _is_media_file(rel):
                files[rel] = -1
    return files


def collect_remote_files(
    serial: str, remote_dir: str, adb: str = "adb",
) -> dict[str, int]:
    """Collect remote media files with sizes.

    Returns dict mapping relative path to file size in bytes.
    Size of -1 means size is unknown (fallback mode).
    """
    prefix = remote_dir.rstrip("/") + "/"

    stat_result = _collect_with_stat(serial, remote_dir, prefix, adb)
    if stat_result is not None:
        return stat_result
    return _collect_paths_only(serial, remote_dir, prefix, adb)


def ensure_remote_dir(serial: str, remote_dir: str, adb: str = "adb") -> None:
    """Create remote directory (mkdir -p)."""
    subprocess.run(
        [adb, "-s", serial, "shell", "mkdir", "-p", remote_dir],
        capture_output=True, check=True,
    )


def push_file(
    local: Path, serial: str, remote: str, adb: str = "adb",
) -> None:
    """Push a single file to device via adb push."""
    result = subprocess.run(
        [adb, "-s", serial, "push", str(local), remote],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"adb push failed: {result.stderr.strip()}")


def _sync_action(local_path: Path, remote_size: int | None) -> str | None:
    """Determine sync action for a file.

    Returns "SYNC" for new files, "UPDATE" for size-mismatched files,
    or None if the file should be skipped (already up-to-date).
    """
    if remote_size is None:
        return "SYNC"
    if remote_size == -1 or remote_size == local_path.stat().st_size:
        return None
    return "UPDATE"


def sync_library(
    config: Config,
    device_serial: str | None = None,
    sd_card_path: str | None = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Sync library media files to Android SD card.

    Returns (synced_count, skipped_count).
    """
    opus_root = config.opus_root
    if not opus_root.exists():
        print(f"Error: Opus directory not found: {opus_root}", file=sys.stderr)
        sys.exit(1)

    serial = _resolve_device(device_serial, config.adb)
    sd_card = _resolve_sd_card(sd_card_path, serial, config.adb)
    remote_base = f"{sd_card}/{config.sync_remote_music_dir}"

    # Collect local media files (relative to opus_root)
    local_files: list[str] = sorted(
        str(f.relative_to(opus_root))
        for f in opus_root.rglob("*")
        if f.is_file() and _is_media_file(f.name)
    )

    if not local_files:
        print("No media files found in library")
        return 0, 0

    # Collect remote files for diff
    print(f"Scanning remote: {remote_base}")
    remote_files = collect_remote_files(serial, remote_base, config.adb)

    synced = 0
    skipped = 0
    for rel_path in local_files:
        local_path = opus_root / rel_path
        action = _sync_action(local_path, remote_files.get(rel_path))

        if action is None:
            skipped += 1
            continue

        remote_path = f"{remote_base}/{rel_path}"

        if dry_run:
            print(f"  [{action}] {rel_path}")
            synced += 1
            continue

        remote_parent = remote_path.rsplit("/", 1)[0]
        ensure_remote_dir(serial, remote_parent, config.adb)

        logger.info("Pushing: %s", rel_path)
        print(f"  [{action}] {rel_path}")
        push_file(local_path, serial, remote_path, config.adb)
        synced += 1

    return synced, skipped
