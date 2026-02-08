from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# FileOps $replace() table for title/album in filenames
FILENAME_REPLACE_TITLE: list[tuple[str, str]] = [
    ("~", "\uff5e"),   # ～
    ("*", "\uff0a"),   # ＊
    ("\u2215", "\uff0f"),  # ∕ → ／
    (":", "\uff1a"),   # ：
    (">", "\uff1e"),   # ＞
    ("<", "\uff1c"),   # ＜
    ("\u00d8", "O"),   # Ø → O
    ("\u00c0", "A"),   # À → A
    ("\u00f4", "o"),   # ô → o
    ("\u00e8", "e"),   # è → e
    ("\u00e9", "e"),   # é → e
    ("\u00eb", "e"),   # ë → e
    ("\u3094", "\u3046"),  # ゔ → う
]

# FileOps $replace() table for album artist in filenames
FILENAME_REPLACE_ALBUMARTIST: list[tuple[str, str]] = [
    (":", "\uff1a"),   # ：
    ("*", "\uff0a"),   # ＊
]

# Additional replacement: ? → ？ (observed in existing library)
FILENAME_REPLACE_EXTRA: list[tuple[str, str]] = [
    ("?", "\uff1f"),   # ？
]

VALIS_MEMBERS = ["VALIS", "CHINO", "MYU", "NEFFY", "NINA", "RARA", "VITTE"]


def _apply_replace(s: str, table: list[tuple[str, str]]) -> str:
    for old, new in table:
        s = s.replace(old, new)
    return s


def sanitize_title_for_filename(title: str) -> str:
    """Apply FileOps replacement table to title for filename generation."""
    s = unicodedata.normalize("NFC", title)
    s = _apply_replace(s, FILENAME_REPLACE_TITLE)
    s = _apply_replace(s, FILENAME_REPLACE_EXTRA)
    return s


def sanitize_albumartist_for_filename(albumartist: str) -> str:
    """Apply FileOps replacement table to album artist for filename generation."""
    s = unicodedata.normalize("NFC", albumartist)
    s = _apply_replace(s, FILENAME_REPLACE_ALBUMARTIST)
    return s


def sanitize_album_for_filename(album: str) -> str:
    """Apply FileOps replacement table to album for filename generation."""
    s = unicodedata.normalize("NFC", album)
    s = _apply_replace(s, FILENAME_REPLACE_TITLE)
    s = _apply_replace(s, FILENAME_REPLACE_EXTRA)
    return s


@dataclass
class TrackMetadata:
    """Parsed metadata for a single track."""

    title: str  # Full display title (NFC, with Cover/feat./Live etc.)
    artists: list[str]  # Multiple artist values
    album: str  # e.g. "花譜のお歌"
    album_artist: str  # e.g. "花譜"
    category: str  # e.g. "神椿Studio"
    track_number: int = 0  # Auto-assigned later
    r128_track_gain: int | None = None  # Q7.8 (1/256 dB units)
    artwork_path: Path | None = None
    is_cover: bool = False
    is_live: bool = False
    live_event: str = ""  # e.g. "喝采カーテンコール"
    original_artist: str = ""  # Original song artist for covers
    channel_name: str = ""  # YouTube channel directory name

    @property
    def tag_title(self) -> str:
        """Title for Vorbis Comment TITLE tag (NFC normalized)."""
        return unicodedata.normalize("NFC", self.title)

    @property
    def filename_title(self) -> str:
        """Title sanitized for filename."""
        return sanitize_title_for_filename(self.title)

    @property
    def opus_filename(self) -> str:
        """Final opus filename: '<track>. <title>.opus'"""
        return f"{self.track_number}. {self.filename_title}.opus"

    @property
    def webm_filename(self) -> str:
        """Final webm filename: '<track>. <title>.webm'"""
        return f"{self.track_number}. {self.filename_title}.webm"


@dataclass
class SourceFiles:
    """A pair of downloaded source files (webm + m4a)."""

    webm: Path
    m4a: Path
    channel_dir: str  # Channel directory name (e.g. "KAF")
    epoch: str  # Epoch timestamp from filename
    raw_title: str  # Original YouTube title from filename


@dataclass
class ProcessingResult:
    """Result of processing a single track."""

    source: SourceFiles
    metadata: TrackMetadata
    opus_player_path: Path | None = None  # /Volumes/musics/Opus/...
    opus_original_path: Path | None = None  # /Volumes/musics/Original/.../Opus/...
    webm_original_path: Path | None = None  # /Volumes/musics/Original/.../Original/...
    errors: list[str] = field(default_factory=list)
