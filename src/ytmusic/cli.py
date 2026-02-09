"""CLI entry point for ytmusic."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Config, find_config
from .downloader import download
from .parser import diagnose_parse_failure, parse_title
from .pipeline import discover_files, build_metadata, run_pipeline
from .playlist import generate_all_playlists, generate_artist_playlist, generate_category_playlist


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def cmd_process(args: argparse.Namespace) -> None:
    config = Config.load(find_config(args.config))

    if args.clean_sources:
        source_handling = "clean"
    elif args.move_sources:
        source_handling = "move"
    else:
        source_handling = "keep"

    results = run_pipeline(
        config,
        channel=args.channel,
        dry_run=args.dry_run,
        interactive=args.interactive,
        regenerate_playlists=not args.no_playlist,
        source_handling=source_handling,
    )
    errors = [r for r in results if r.errors]
    if errors:
        print(f"\n{len(errors)} error(s) occurred:")
        for r in errors:
            for e in r.errors:
                print(f"  - {e}")
        sys.exit(1)
    print(f"\nProcessed {len(results)} track(s) successfully")


def cmd_scan(args: argparse.Namespace) -> None:
    config = Config.load(find_config(args.config))
    sources = discover_files(config, args.channel)
    if not sources:
        print("No unprocessed files found")
        return
    print(f"Found {len(sources)} unprocessed file(s):\n")
    failures: list[tuple[str, str, str]] = []  # (raw_title, channel_dir, artist)
    for s in sources:
        ch_config = config.get_channel(s.channel_dir)
        artist = ch_config.artist if ch_config else "?"
        print(f"  [{s.channel_dir}] {s.raw_title}")
        meta = build_metadata(s, config)
        if meta:
            print(f"    → {meta.title} / {', '.join(meta.artists)}")
        else:
            diag = diagnose_parse_failure(s.raw_title, s.channel_dir, artist)
            print(f"    → PARSE ERROR (推定カテゴリ: {diag.likely_category})")
            failures.append((s.raw_title, s.channel_dir, artist))
    if failures:
        print(f"\n--- パース失敗: {len(failures)} 件 ---")
        print("以下を Claude に貼り付けてパターン追加を依頼できます:\n")
        for raw_title, channel_dir, artist in failures:
            diag = diagnose_parse_failure(raw_title, channel_dir, artist)
            print(diag.claude_prompt)
            print()


def cmd_parse(args: argparse.Namespace) -> None:
    config = Config.load(find_config(args.config))
    title = args.title
    ch_config = config.get_channel(args.channel) if args.channel else None
    channel_dir = args.channel or "UNKNOWN"
    channel_artist = ch_config.artist if ch_config else "Unknown"

    result = parse_title(title, channel_artist)
    if result is None:
        diag = diagnose_parse_failure(title, channel_dir, channel_artist)
        print(f"No pattern matched: {title}")
        print(f"推定カテゴリ: {diag.likely_category}")
        if diag.detected_keywords:
            print(f"検出キーワード: {', '.join(diag.detected_keywords)}")
        if diag.structural_features:
            print(f"構造的特徴: {', '.join(diag.structural_features)}")
        print(f"\n--- Claude に貼り付け用プロンプト ---\n")
        print(diag.claude_prompt)
        sys.exit(1)

    print(f"Pattern:  {result.pattern_id}")
    print(f"Title:    {result.title}")
    print(f"Artists:  {result.artists}")
    print(f"Cover:    {result.is_cover}")
    print(f"Live:     {result.is_live}")
    if result.original_artist:
        print(f"Original: {result.original_artist}")
    if result.live_event:
        print(f"Event:    {result.live_event}")


def cmd_playlist(args: argparse.Namespace) -> None:
    config = Config.load(find_config(args.config))
    if not config.playlist_artists and not config.playlist_categories:
        print("No playlists configured. Add [playlists] section to config.", file=sys.stderr)
        sys.exit(1)
    if args.artist:
        if args.artist not in config.playlist_artists:
            print(f"Unknown artist: {args.artist}", file=sys.stderr)
            print(f"Available: {', '.join(config.playlist_artists)}", file=sys.stderr)
            sys.exit(1)
        p = generate_artist_playlist(args.artist, config)
        print(f"Generated: {p}")
    elif args.category:
        if args.category not in config.playlist_categories:
            print(f"Unknown category: {args.category}", file=sys.stderr)
            print(f"Available: {', '.join(config.playlist_categories)}", file=sys.stderr)
            sys.exit(1)
        p = generate_category_playlist(args.category, config)
        print(f"Generated: {p}")
    else:
        generated = generate_all_playlists(config)
        print(f"Generated {len(generated)} playlist(s)")
        for p in generated:
            print(f"  {p.name}")


def cmd_download(args: argparse.Namespace) -> None:
    config = Config.load(find_config(args.config))
    urls: list[str] = []
    if args.url:
        urls.append(args.url)
    if args.urls:
        urls_path = Path(args.urls)
        urls.extend(
            line.strip()
            for line in urls_path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        )
    if not urls:
        print("No URLs specified", file=sys.stderr)
        sys.exit(1)
    print(f"Downloading {len(urls)} URL(s)...")
    download(urls, config)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ytmusic",
        description="YouTube music post-processor",
    )
    parser.add_argument("-c", "--config", help="Config file path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command")

    # process
    p_process = subparsers.add_parser("process", help="Run full pipeline")
    p_process.add_argument("-n", "--dry-run", action="store_true", help="Preview only")
    p_process.add_argument("--channel", help="Process specific channel only")
    p_process.add_argument("-i", "--interactive", action="store_true", help="Confirm each track")
    p_process.add_argument("--no-playlist", action="store_true", help="Skip playlist regeneration")
    source_group = p_process.add_mutually_exclusive_group()
    source_group.add_argument(
        "--move-sources", action="store_true",
        help="Delete source files after processing (Original/ backup kept)",
    )
    source_group.add_argument(
        "--clean-sources", action="store_true",
        help="Delete source files after processing (no backup)",
    )

    # scan
    p_scan = subparsers.add_parser("scan", help="List unprocessed files")
    p_scan.add_argument("--channel", help="Scan specific channel only")

    # parse
    p_parse = subparsers.add_parser("parse", help="Test title parsing")
    p_parse.add_argument("title", help="YouTube title to parse")
    p_parse.add_argument("--channel", help="Channel name for context")

    # playlist
    p_playlist = subparsers.add_parser("playlist", help="Generate m3u8 playlists")
    p_playlist.add_argument("--artist", help="Generate playlist for specific artist")
    p_playlist.add_argument("--category", help="Generate playlist for specific category")

    # download
    p_download = subparsers.add_parser("download", help="Download from YouTube")
    p_download.add_argument("url", nargs="?", help="YouTube URL")
    p_download.add_argument("--urls", help="File with URLs (one per line)")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "process": cmd_process,
        "scan": cmd_scan,
        "parse": cmd_parse,
        "playlist": cmd_playlist,
        "download": cmd_download,
    }
    handlers[args.command](args)
