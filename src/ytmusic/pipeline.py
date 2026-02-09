"""Pipeline orchestration: discover, parse, process, organize."""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

from .audio import calculate_r128_gain, extract_artwork, extract_opus
from .config import Config
from .models import ProcessingResult, SourceFiles, TrackMetadata
from .organizer import compute_paths, get_next_track_number, place_files
from .parser import diagnose_parse_failure, parse_title
from .tagger import tag_opus

logger = logging.getLogger(__name__)


def discover_files(config: Config, channel: str | None = None) -> list[SourceFiles]:
    """Scan youtube_dir for webm+m4a pairs.

    Args:
        config: Configuration.
        channel: If set, only scan this channel directory.

    Returns:
        List of SourceFiles, sorted by epoch.
    """
    youtube_dir = config.youtube_dir
    results: list[SourceFiles] = []

    if channel:
        dirs = [youtube_dir / channel]
    else:
        dirs = sorted(d for d in youtube_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

    for ch_dir in dirs:
        if not ch_dir.exists():
            logger.warning("Channel directory not found: %s", ch_dir)
            continue

        webm_files = sorted(ch_dir.glob("*.webm"))
        for webm in webm_files:
            m4a = webm.with_suffix(".m4a")
            if not m4a.exists():
                logger.warning("No matching m4a for: %s", webm.name)
                continue

            # Parse epoch and title from filename: <epoch>-<title>.webm
            match = re.match(r"(\d+)-(.+)\.webm$", webm.name)
            if not match:
                logger.warning("Unexpected filename format: %s", webm.name)
                continue

            results.append(SourceFiles(
                webm=webm,
                m4a=m4a,
                channel_dir=ch_dir.name,
                epoch=match.group(1),
                raw_title=match.group(2),
            ))

    return results


def build_metadata(
    source: SourceFiles,
    config: Config,
) -> TrackMetadata | None:
    """Parse source file title and build TrackMetadata."""
    ch_config = config.get_channel(source.channel_dir)
    if ch_config is None:
        logger.error("Unknown channel: %s", source.channel_dir)
        return None

    result = parse_title(source.raw_title, ch_config.artist)
    if result is None:
        logger.error("Failed to parse title: %s", source.raw_title)
        return None

    album = config.album_name(ch_config.artist)

    return TrackMetadata(
        title=result.title,
        artists=result.artists,
        album=album,
        album_artist=ch_config.artist,
        category=ch_config.category,
        is_cover=result.is_cover,
        is_live=result.is_live,
        live_event=result.live_event,
        original_artist=result.original_artist,
        channel_name=source.channel_dir,
    )


def process_track(
    source: SourceFiles,
    metadata: TrackMetadata,
    config: Config,
    dry_run: bool = False,
) -> ProcessingResult:
    """Process a single track through the full pipeline.

    Steps: EXTRACT → ARTWORK → R128 → TAG → ORGANIZE
    """
    result = ProcessingResult(source=source, metadata=metadata)

    # Compute track number
    paths = compute_paths(metadata, config)
    album_dir = paths["album_dir"]
    metadata.track_number = get_next_track_number(album_dir)

    if dry_run:
        # Recompute paths with track number set
        paths = compute_paths(metadata, config)
        result.opus_player_path = paths["opus_player"]
        result.opus_original_path = paths["opus_original"]
        result.webm_original_path = paths["webm_original"]
        return result

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # EXTRACT: webm → Opus
        tmp_opus = tmp / "audio.opus"
        try:
            extract_opus(source.webm, tmp_opus, config.ffmpeg)
        except Exception as e:
            result.errors.append(f"Extract failed: {e}")
            return result

        # ARTWORK: m4a → image
        try:
            artwork = extract_artwork(source.m4a, config.atomicparsley)
            metadata.artwork_path = artwork
        except Exception as e:
            logger.warning("Artwork extraction failed: %s", e)

        # R128: calculate gain
        try:
            gain = calculate_r128_gain(tmp_opus, config.ffmpeg)
            metadata.r128_track_gain = gain
        except Exception as e:
            logger.warning("R128 calculation failed: %s", e)

        # TAG: write metadata
        try:
            tag_opus(tmp_opus, metadata)
        except Exception as e:
            result.errors.append(f"Tagging failed: {e}")
            return result

        # ORGANIZE: place files
        try:
            dest = place_files(tmp_opus, source.webm, metadata, config)
            result.opus_player_path = dest["opus_player"]
            result.opus_original_path = dest["opus_original"]
            result.webm_original_path = dest["webm_original"]
        except Exception as e:
            result.errors.append(f"Organize failed: {e}")

    return result


def run_pipeline(
    config: Config,
    channel: str | None = None,
    dry_run: bool = False,
    interactive: bool = False,
    regenerate_playlists: bool = True,
) -> list[ProcessingResult]:
    """Run the full pipeline on all discovered files.

    Returns list of ProcessingResults.
    """
    sources = discover_files(config, channel)
    if not sources:
        logger.info("No files to process")
        return []

    logger.info("Found %d file(s) to process", len(sources))
    results: list[ProcessingResult] = []

    # Pre-compute track numbers per album to avoid conflicts
    album_next: dict[str, int] = {}

    for i, source in enumerate(sources, 1):
        metadata = build_metadata(source, config)
        if metadata is None:
            ch_config = config.get_channel(source.channel_dir)
            ch_artist = ch_config.artist if ch_config else "Unknown"
            diag = diagnose_parse_failure(
                source.raw_title, source.channel_dir, ch_artist,
            )
            results.append(ProcessingResult(
                source=source,
                metadata=TrackMetadata(
                    title="PARSE_ERROR",
                    artists=[],
                    album="",
                    album_artist="",
                    category="",
                ),
                errors=[
                    f"Failed to parse: {source.raw_title} "
                    f"(推定カテゴリ: {diag.likely_category})",
                    diag.claude_prompt,
                ],
            ))
            continue

        # Get or compute next track number for this album
        paths = compute_paths(metadata, config)
        album_key = str(paths["album_dir"])
        if album_key not in album_next:
            album_next[album_key] = get_next_track_number(paths["album_dir"])
        metadata.track_number = album_next[album_key]
        album_next[album_key] += 1

        # Display info
        _print_track_info(i, len(sources), source, metadata, config, dry_run)

        if interactive:
            response = input("  Process? [Y/n/e(dit)] ").strip().lower()
            if response == "n":
                logger.info("  Skipped")
                continue
            if response == "e":
                metadata.title = input(f"  Title [{metadata.title}]: ").strip() or metadata.title
                artists_str = input(f"  Artists [{', '.join(metadata.artists)}]: ").strip()
                if artists_str:
                    metadata.artists = [a.strip() for a in artists_str.split(",")]

        if dry_run:
            # Recompute with final track number
            final_paths = compute_paths(metadata, config)
            result = ProcessingResult(
                source=source,
                metadata=metadata,
                opus_player_path=final_paths["opus_player"],
                opus_original_path=final_paths["opus_original"],
                webm_original_path=final_paths["webm_original"],
            )
            results.append(result)
            continue

        result = process_track(source, metadata, config)
        results.append(result)
        if result.errors:
            for err in result.errors:
                logger.error("  ERROR: %s", err)

    if regenerate_playlists and not dry_run and results:
        from .playlist import generate_playlists_for_results

        generated = generate_playlists_for_results(results, config)
        for p in generated:
            logger.info("Regenerated playlist: %s", p.name)

    return results


def _print_track_info(
    idx: int,
    total: int,
    source: SourceFiles,
    metadata: TrackMetadata,
    config: Config,
    dry_run: bool,
) -> None:
    """Print track processing info."""
    paths = compute_paths(metadata, config)
    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"\n{prefix}[{idx}/{total}] {source.channel_dir} / {source.raw_title}")
    print(f"  Title:   {metadata.title}")
    print(f"  Artist:  {', '.join(metadata.artists)}")
    print(f"  Album:   {metadata.album}")
    print(f"  Track:   {metadata.track_number}")
    print(f"  Opus  →  {paths['opus_player']}")
    print(f"  Orig  →  {paths['webm_original']}")
