"""Playlist generation: collect tracks and write m3u8 files."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from .config import Config
from .models import ProcessingResult

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".opus", ".m4a"}


def _read_exclude(directory: Path) -> set[str]:
    """Read .exclude file and return set of filenames to exclude."""
    exclude_file = directory / ".exclude"
    if not exclude_file.exists():
        return set()
    return {
        line.strip()
        for line in exclude_file.read_text().splitlines()
        if line.strip()
    }


def _track_sort_key(path: Path) -> tuple[int, str]:
    """Sort key: extract track number prefix, then by name."""
    m = re.match(r"(\d+)\.\s", path.name)
    if m:
        return (int(m.group(1)), path.name)
    return (0, path.name)


def _collect_audio_files(directory: Path, exclude: set[str]) -> list[Path]:
    """Collect audio files from a single directory, excluding named files."""
    tracks = [
        entry for entry in directory.iterdir()
        if entry.is_file()
        and entry.suffix in AUDIO_EXTENSIONS
        and entry.name not in exclude
    ]
    tracks.sort(key=_track_sort_key)
    return tracks


def _collect_tracks(directory: Path, playlists_base: Path) -> list[str]:
    """Collect audio tracks from directory, respecting .exclude files.

    Returns list of relative paths from playlists_base, sorted by track number.
    """
    if not directory.exists():
        return []

    exclude_file = directory / ".exclude"
    if exclude_file.exists():
        # .exclude present (even if empty): collect from this directory only
        exclude = _read_exclude(directory)
        tracks = _collect_audio_files(directory, exclude)
        return [os.path.relpath(t, playlists_base) for t in tracks]

    # No .exclude: recurse into subdirectories if any exist
    subdirs = sorted(
        d for d in directory.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    if subdirs:
        result: list[str] = []
        for subdir in subdirs:
            result.extend(_collect_tracks(subdir, playlists_base))
        return result

    # Leaf directory without .exclude: collect all audio files
    tracks = _collect_audio_files(directory, exclude=set())
    return [os.path.relpath(t, playlists_base) for t in tracks]


def write_playlist(tracks: list[str], output_path: Path) -> None:
    """Write m3u8 playlist file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#\n")
        for track in tracks:
            f.write(f"{track}\n")


def _generate_playlist(
    name: str,
    source_dir_rel: str,
    filename: str,
    config: Config,
) -> Path:
    """Generate a single playlist from a source directory.

    Args:
        name: Playlist name (for logging).
        source_dir_rel: Source directory relative to opus_root.
        filename: Output filename (e.g. "Artist.m3u8" or "00_Category.m3u8").
        config: Configuration.
    """
    source_dir = config.opus_root / source_dir_rel
    tracks = _collect_tracks(source_dir, config.playlists_base)
    output_path = config.playlist_output_path / filename
    write_playlist(tracks, output_path)
    logger.info("Generated playlist: %s (%d tracks)", output_path.name, len(tracks))
    return output_path


def generate_artist_playlist(name: str, config: Config) -> Path:
    """Generate playlist for a single artist."""
    return _generate_playlist(
        name, config.playlist_artists[name], f"{name}.m3u8", config,
    )


def generate_category_playlist(name: str, config: Config) -> Path:
    """Generate playlist for a category (prefixed with 00_)."""
    return _generate_playlist(
        name, config.playlist_categories[name], f"00_{name}.m3u8", config,
    )


def generate_all_playlists(config: Config) -> list[Path]:
    """Generate all configured playlists."""
    generated = [
        generate_artist_playlist(name, config)
        for name in config.playlist_artists
    ]
    generated.extend(
        generate_category_playlist(name, config)
        for name in config.playlist_categories
    )
    return generated


def generate_playlists_for_results(
    results: list[ProcessingResult],
    config: Config,
) -> list[Path]:
    """Regenerate playlists affected by processing results."""
    if not config.playlist_artists and not config.playlist_categories:
        return []

    affected_categories: set[str] = set()
    affected_artists: set[str] = set()

    for r in results:
        if r.errors:
            continue
        category = r.metadata.category
        album_artist = r.metadata.album_artist

        for cat_name, cat_dir in config.playlist_categories.items():
            if category == cat_name or cat_dir.startswith(category) or category.startswith(cat_dir):
                affected_categories.add(cat_name)

        if album_artist in config.playlist_artists:
            affected_artists.add(album_artist)

    generated: list[Path] = []
    for name in affected_artists:
        generated.append(generate_artist_playlist(name, config))
    for name in affected_categories:
        generated.append(generate_category_playlist(name, config))
    return generated
