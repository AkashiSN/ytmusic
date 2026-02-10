"""ADB sync: transfer media files to Android SD card."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from .config import Config
from .models import sanitize_albumartist_for_filename

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


def collect_remote_files(
    serial: str, remote_dir: str, adb: str = "adb",
) -> set[str]:
    """Collect set of relative media file paths on remote device."""
    result = subprocess.run(
        [adb, "-s", serial, "shell",
         "find", remote_dir, "-type", "f"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Directory may not exist yet
        return set()
    prefix = remote_dir.rstrip("/") + "/"
    paths: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            rel = unicodedata.normalize("NFC", line[len(prefix):])
            if _is_media_file(rel):
                paths.add(rel)
    return paths


def collect_remote_playlist_sizes(
    serial: str, remote_dir: str, adb: str = "adb",
) -> dict[str, int]:
    """Collect remote .m3u8 file sizes as {relative_path: size_bytes}.

    Uses ``wc -c`` (POSIX) for broad Android device compatibility.
    Returns an empty dict on failure (graceful fallback).
    """
    result = subprocess.run(
        [adb, "-s", serial, "shell",
         "find", remote_dir, "-name", "*.m3u8",
         "-exec", "wc", "-c", "{}", "+"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {}
    prefix = remote_dir.rstrip("/") + "/"
    sizes: dict[str, int] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        path = parts[1]
        if path.startswith(prefix):
            rel = unicodedata.normalize("NFC", path[len(prefix):])
            sizes[rel] = size
    return sizes


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


def _collect_sync_targets(config: Config) -> list[str]:
    """Collect local media files limited to configured channels and playlists."""
    opus_root = config.opus_root
    files: set[str] = set()

    for ch in config.channels.values():
        artist_dir = sanitize_albumartist_for_filename(ch.artist)
        target = opus_root / ch.category / artist_dir
        if target.is_dir():
            for f in target.rglob("*"):
                if f.is_file() and _is_media_file(f.name):
                    files.add(unicodedata.normalize("NFC", str(f.relative_to(opus_root))))

    playlist_dir = opus_root / config.playlist_output_dir
    if playlist_dir.is_dir():
        for f in playlist_dir.rglob("*"):
            if f.is_file() and _is_media_file(f.name):
                files.add(unicodedata.normalize("NFC", str(f.relative_to(opus_root))))

    return sorted(files)


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
    local_files = _collect_sync_targets(config)

    if not local_files:
        print("No media files found in library")
        return 0, 0

    # Collect remote files for diff
    print(f"Scanning remote: {remote_base}")
    remote_files = collect_remote_files(serial, remote_base, config.adb)
    remote_playlist_sizes = collect_remote_playlist_sizes(
        serial, remote_base, config.adb,
    )

    synced = 0
    skipped = 0
    for rel_path in local_files:
        local_path = opus_root / rel_path
        remote_path = f"{remote_base}/{rel_path}"
        is_playlist = rel_path.endswith(".m3u8")

        # Determine if file needs syncing
        if rel_path not in remote_files:
            label = "NEW"
        elif is_playlist:
            local_size = local_path.stat().st_size
            if rel_path in remote_playlist_sizes:
                remote_size = remote_playlist_sizes[rel_path]
                if local_size == remote_size:
                    skipped += 1
                    continue
                reason = f"size {remote_size} -> {local_size}"
            else:
                reason = "remote size unknown"
            label = f"UPDATE: {reason}"
        else:
            skipped += 1
            continue

        if dry_run:
            print(f"  [{label}] {rel_path}")
            synced += 1
            continue

        # Ensure parent directory exists on remote
        remote_parent = remote_path.rsplit("/", 1)[0]
        ensure_remote_dir(serial, remote_parent, config.adb)

        logger.info("Pushing: %s", rel_path)
        print(f"  [{label}] {rel_path}")
        push_file(local_path, serial, remote_path, config.adb)
        synced += 1

    return synced, skipped


def sync_files(
    files: list[Path],
    config: Config,
    device_serial: str | None = None,
    sd_card_path: str | None = None,
) -> int:
    """Sync specific files to Android SD card (for post-process auto-sync).

    Args:
        files: List of absolute paths to .opus files in the library.
        config: Configuration.
        device_serial: Optional device serial to use.
        sd_card_path: Optional SD card path to use.

    Returns:
        Number of files synced.
    """
    opus_root = config.opus_root

    serial = _resolve_device(device_serial, config.adb)
    sd_card = _resolve_sd_card(sd_card_path, serial, config.adb)
    remote_base = f"{sd_card}/{config.sync_remote_music_dir}"

    synced = 0
    for local_path in files:
        try:
            rel_path = str(local_path.relative_to(opus_root))
        except ValueError:
            logger.warning("File not under opus_root, skipping: %s", local_path)
            continue

        remote_path = f"{remote_base}/{rel_path}"
        remote_parent = remote_path.rsplit("/", 1)[0]
        ensure_remote_dir(serial, remote_parent, config.adb)

        logger.info("Pushing: %s", rel_path)
        print(f"  [PUSH] {rel_path}")
        push_file(local_path, serial, remote_path, config.adb)
        synced += 1

    return synced
