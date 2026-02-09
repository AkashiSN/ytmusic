"""File organizer: track numbering, path calculation, file placement."""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from .config import Config
from .models import (
    TrackMetadata,
    sanitize_album_for_filename,
    sanitize_albumartist_for_filename,
    sanitize_title_for_filename,
)

logger = logging.getLogger(__name__)


def get_next_track_number(album_dir: Path) -> int:
    """Find the maximum track number in album_dir and return max+1.

    Scans all .opus files matching the pattern '<number>. <title>.opus'.
    """
    max_num = 0
    if album_dir.exists():
        for f in album_dir.iterdir():
            if f.suffix == ".opus":
                m = re.match(r"(\d+)\.\s", f.name)
                if m:
                    num = int(m.group(1))
                    if num > max_num:
                        max_num = num
    return max_num + 1


def compute_paths(metadata: TrackMetadata, config: Config) -> dict[str, Path]:
    """Compute all destination paths for a track.

    Returns dict with keys:
        - opus_player: /Volumes/musics/Opus/<Cat>/<Artist>/<Album>/<file>.opus
        - webm_original: /Volumes/musics/Original/<Cat>/<Artist>/<Album>/<file>.webm
        - album_dir: The album directory (for track number scanning)
    """
    lib = config.library_dir
    cat = metadata.category
    artist_dir = sanitize_albumartist_for_filename(metadata.album_artist)
    album_dir = sanitize_album_for_filename(metadata.album)
    opus_fn = metadata.opus_filename
    webm_fn = metadata.webm_filename

    return {
        "opus_player": lib / "Opus" / cat / artist_dir / album_dir / opus_fn,
        "webm_original": lib / "Original" / cat / artist_dir / album_dir / webm_fn,
        "album_dir": lib / "Opus" / cat / artist_dir / album_dir,
    }


def place_files(
    opus_path: Path,
    webm_path: Path,
    metadata: TrackMetadata,
    config: Config,
    dry_run: bool = False,
    source_handling: str = "keep",
    m4a_path: Path | None = None,
) -> dict[str, Path]:
    """Move/copy files to their final library locations.

    Args:
        opus_path: Tagged Opus file to place.
        webm_path: Original webm file.
        metadata: Track metadata (with track_number set).
        config: Configuration.
        dry_run: If True, only log what would happen.
        source_handling: "keep" (default), "move", or "clean".
        m4a_path: Path to m4a source file (for cleanup).

    Returns:
        Dict of destination paths.
    """
    paths = compute_paths(metadata, config)

    if dry_run:
        logger.info("  [DRY-RUN] Opus  → %s", paths["opus_player"])
        if source_handling != "clean":
            logger.info("  [DRY-RUN] Orig  → %s", paths["webm_original"])
        if source_handling in ("move", "clean"):
            logger.info("  [DRY-RUN] Delete sources: %s", webm_path.parent)
        return paths

    # Create directories
    paths["opus_player"].parent.mkdir(parents=True, exist_ok=True)

    # Move tagged opus to player directory
    shutil.move(str(opus_path), str(paths["opus_player"]))
    logger.info("Moved Opus → %s", paths["opus_player"])

    # Copy webm to Original/ (unless clean mode)
    if source_handling != "clean":
        paths["webm_original"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(webm_path), str(paths["webm_original"]))
        logger.info("Copied webm → %s", paths["webm_original"])
    else:
        paths["webm_original"] = None  # type: ignore[assignment]

    # Delete source files if requested
    if source_handling in ("move", "clean"):
        for src in (webm_path, m4a_path, metadata.artwork_path):
            if src and src.exists():
                src.unlink()
                logger.info("Deleted source: %s", src)

    return paths
