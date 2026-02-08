"""CLI entry point for ytmusic."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Config, find_config
from .downloader import download, get_chrome_user_agent, update_config_ua
from .parser import diagnose_parse_failure, parse_title
from .pipeline import discover_files, build_metadata, run_pipeline


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def cmd_process(args: argparse.Namespace) -> None:
    config = Config.load(find_config(args.config))
    results = run_pipeline(
        config,
        channel=args.channel,
        dry_run=args.dry_run,
        interactive=args.interactive,
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


def cmd_update_ua(args: argparse.Namespace) -> None:
    config_path = find_config(args.config)
    ua = update_config_ua(config_path)
    if ua:
        print(f"Updated user_agent in {config_path}: {ua}")
    else:
        print("Failed to detect Chrome user agent", file=sys.stderr)
        sys.exit(1)


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

    # scan
    p_scan = subparsers.add_parser("scan", help="List unprocessed files")
    p_scan.add_argument("--channel", help="Scan specific channel only")

    # parse
    p_parse = subparsers.add_parser("parse", help="Test title parsing")
    p_parse.add_argument("title", help="YouTube title to parse")
    p_parse.add_argument("--channel", help="Channel name for context")

    # download
    p_download = subparsers.add_parser("download", help="Download from YouTube")
    p_download.add_argument("url", nargs="?", help="YouTube URL")
    p_download.add_argument("--urls", help="File with URLs (one per line)")

    # update-ua
    subparsers.add_parser("update-ua", help="Update Chrome user agent in config")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "process": cmd_process,
        "scan": cmd_scan,
        "parse": cmd_parse,
        "download": cmd_download,
        "update-ua": cmd_update_ua,
    }
    handlers[args.command](args)
