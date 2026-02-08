"""yt-dlp wrapper and User-Agent auto-detection."""

from __future__ import annotations

import logging
import plistlib
import subprocess
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)


def get_chrome_user_agent() -> str | None:
    """Read the Chrome version from the local application and construct a UA string."""
    chrome_plist = Path(
        "/Applications/Google Chrome.app/Contents/Info.plist"
    )
    if not chrome_plist.exists():
        logger.warning("Chrome not found at %s", chrome_plist)
        return None

    with open(chrome_plist, "rb") as f:
        plist = plistlib.load(f)

    version = plist.get("CFBundleShortVersionString")
    if not version:
        return None

    ua = (
        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{version} Safari/537.36"
    )
    return ua


def update_config_ua(config_path: Path) -> str | None:
    """Detect Chrome UA and update config.toml in-place."""
    ua = get_chrome_user_agent()
    if ua is None:
        logger.error("Could not detect Chrome user agent")
        return None

    text = config_path.read_text(encoding="utf-8")
    import re
    new_text = re.sub(
        r'(user_agent\s*=\s*)"[^"]*"',
        f'\\1"{ua}"',
        text,
    )
    config_path.write_text(new_text, encoding="utf-8")
    logger.info("Updated user_agent in %s: %s", config_path, ua)
    return ua


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
