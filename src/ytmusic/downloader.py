"""yt-dlp wrapper."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


def download(
    urls: list[str],
    config: Config,
    output_dir: Path | None = None,
) -> None:
    """Download audio from YouTube URLs using yt-dlp.

    Downloads both webm (audio) and m4a (with embedded thumbnail for artwork extraction).
    """
    if output_dir is None:
        output_dir = config.youtube_dir

    failed: list[str] = []
    for url in urls:
        output_template = str(output_dir / "%(uploader)s" / "%(epoch)s-%(title)s.%(ext)s")
        cmd = [
            config.yt_dlp,
            "--user-agent", config.user_agent,
            "--referer", config.referer,
            "--extract-audio",
            "--format", "ba[ext=webm]",
            "--keep-video",
            "--audio-format", "aac",
            "--embed-thumbnail",
            "--convert-thumbnails", "jpg",
            "--output", output_template,
            url,
        ]
        logger.info("Downloading: %s", url)
        result = subprocess.run(cmd)
        if result.returncode != 0:
            logger.error("Failed to download: %s", url)
            failed.append(url)

    if failed:
        logger.error("%d/%d download(s) failed", len(failed), len(urls))
        for url in failed:
            print(f"  FAILED: {url}")
        raise RuntimeError(f"{len(failed)} download(s) failed")
