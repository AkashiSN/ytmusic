from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ENV_CONFIG = "YTMUSIC_CONFIG"
DEFAULT_CONFIG_DIR = Path("~/.config/ytmusic").expanduser()
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"


def find_config(cli_path: str | None = None) -> Path:
    """Resolve config path: --config flag > $YTMUSIC_CONFIG > ~/.config/ytmusic/config.toml"""
    if cli_path:
        p = Path(cli_path)
        if not p.exists():
            print(f"Error: config not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p

    env = os.environ.get(ENV_CONFIG)
    if env:
        p = Path(env).expanduser()
        if not p.exists():
            print(f"Error: ${ENV_CONFIG} points to missing file: {p}", file=sys.stderr)
            sys.exit(1)
        return p

    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH

    print(
        f"Error: config.toml not found.\n"
        f"  Place it at: {DEFAULT_CONFIG_PATH}\n"
        f"  Or set ${ENV_CONFIG} or use --config flag.",
        file=sys.stderr,
    )
    sys.exit(1)


@dataclass
class ChannelConfig:
    artist: str
    category: str


@dataclass
class Config:
    config_path: Path
    youtube_dir: Path
    library_dir: Path
    ffmpeg: str
    atomicparsley: str
    yt_dlp: str
    user_agent: str
    referer: str
    album_format: str
    channels: dict[str, ChannelConfig] = field(default_factory=dict)

    def get_channel(self, channel_dir: str) -> ChannelConfig | None:
        return self.channels.get(channel_dir)

    def album_name(self, artist: str) -> str:
        return self.album_format.format(artist=artist)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        if path is None:
            path = find_config()
        with open(path, "rb") as f:
            data = tomllib.load(f)

        paths = data.get("paths", {})
        tools = data.get("tools", {})
        download = data.get("download", {})
        album = data.get("album", {})

        channels: dict[str, ChannelConfig] = {}
        for ch_name, ch_data in data.get("channels", {}).items():
            channels[ch_name] = ChannelConfig(
                artist=ch_data["artist"],
                category=ch_data["category"],
            )

        return cls(
            config_path=path,
            youtube_dir=Path(paths.get("youtube_dir", "~/Music/Youtube")).expanduser(),
            library_dir=Path(paths.get("library_dir", "/Volumes/musics")),
            ffmpeg=tools.get("ffmpeg", "ffmpeg"),
            atomicparsley=str(Path(tools.get("atomicparsley", "AtomicParsley")).expanduser()),
            yt_dlp=tools.get("yt-dlp", "yt-dlp"),
            user_agent=download.get("user_agent", ""),
            referer=download.get("referer", "https://www.youtube.com/"),
            album_format=album.get("format", "{artist}のお歌"),
            channels=channels,
        )
