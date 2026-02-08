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
        - opus_original: /Volumes/musics/Original/<Cat>/<Artist>/<Album>/Opus/<file>.opus
        - webm_original: /Volumes/musics/Original/<Cat>/<Artist>/<Album>/Original/<file>.webm
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
        "opus_original": lib / "Original" / cat / artist_dir / album_dir / "Opus" / opus_fn,
        "webm_original": lib / "Original" / cat / artist_dir / album_dir / "Original" / webm_fn,
        "album_dir": lib / "Opus" / cat / artist_dir / album_dir,
    }


def place_files(
    opus_path: Path,
    webm_path: Path,
    metadata: TrackMetadata,
    config: Config,
    dry_run: bool = False,
) -> dict[str, Path]:
    """Move/copy files to their final library locations.

    Args:
        opus_path: Tagged Opus file to place.
        webm_path: Original webm file.
        metadata: Track metadata (with track_number set).
        config: Configuration.
        dry_run: If True, only log what would happen.

    Returns:
        Dict of destination paths.
    """
    paths = compute_paths(metadata, config)

    if dry_run:
        logger.info("  [DRY-RUN] Opus  → %s", paths["opus_player"])
        logger.info("  [DRY-RUN] Copy  → %s", paths["opus_original"])
        logger.info("  [DRY-RUN] Orig  → %s", paths["webm_original"])
        return paths

    # Create directories
    for key in ("opus_player", "opus_original", "webm_original"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)

    # Move tagged opus to player directory
    shutil.move(str(opus_path), str(paths["opus_player"]))
    logger.info("Moved Opus → %s", paths["opus_player"])

    # Copy to Original/Opus
    shutil.copy2(str(paths["opus_player"]), str(paths["opus_original"]))
    logger.info("Copied Opus → %s", paths["opus_original"])

    # Move webm to Original/Original
    shutil.move(str(webm_path), str(paths["webm_original"]))
    logger.info("Moved webm → %s", paths["webm_original"])

    return paths
