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

    for url in urls:
        output_template = str(output_dir / "%(uploader)s" / "%(epoch)s-%(title)s.%(ext)s")
        cmd = [
            config.yt_dlp,
            "--user-agent", config.user_agent,
            "--referer", config.referer,
            "--extract-audio",
            "--format", "ba[ext=webm]",
            "--keep-video",
            "--audio-format", "alac",
            "--embed-thumbnail",
            "--output", output_template,
            url,
        ]
        logger.info("Downloading: %s", url)
        subprocess.run(cmd, check=True)
