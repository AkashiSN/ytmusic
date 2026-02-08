"""Title parser: extract metadata from YouTube video titles.

17 patterns applied in priority order; first match wins.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .models import VALIS_MEMBERS


@dataclass
class ParseResult:
    """Raw parse output before channel config is applied."""

    title: str  # Display title (e.g. "1ピース (Cover)")
    artists: list[str]  # Performer(s)
    is_cover: bool = False
    is_live: bool = False
    live_event: str = ""
    original_artist: str = ""
    pattern_id: str = ""  # Which pattern matched (for debugging)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _strip(s: str) -> str:
    return s.strip()


def _split_artists(name: str) -> list[str]:
    """Split artist names joined by × into a list."""
    parts = re.split(r"\s*[×]\s*", name)
    return [_strip(p) for p in parts if _strip(p)]


def _parse_feat(title: str) -> tuple[str, str]:
    """Extract 'feat. <name>' from title, return (cleaned_title_part, feat_name)."""
    m = re.search(r"\s+feat\.\s*(.+)$", title)
    if m:
        return title[: m.start()], _strip(m.group(1))
    return title, ""


def parse_title(raw_title: str, channel_artist: str) -> ParseResult | None:
    """Parse a YouTube title into structured metadata.

    Args:
        raw_title: The YouTube video title (from filename).
        channel_artist: The artist name from config for this channel.

    Returns:
        ParseResult or None if no pattern matches.
    """
    title = _nfc(raw_title.strip())

    # Pre-processing: remove trailing (from <event>) and extract live_event
    live_event = ""
    m_from = re.search(r"\s*\(from\s+(.+?)\)\s*$", title)
    if m_from:
        live_event = m_from.group(1)
        title = title[: m_from.start()]

    # Pre-processing: remove trailing 'with <name>' and save as feat
    with_name = ""
    m_with = re.search(r"\s+with\s+(.+?)\s*$", title)
    if m_with:
        with_name = _strip(m_with.group(1))
        title = title[: m_with.start()]

    # Try each pattern in priority order
    for pattern_fn in _PATTERNS:
        result = pattern_fn(title, channel_artist)
        if result is not None:
            # Apply with_name to title and artists
            if with_name:
                result.title = f"{result.title} with {with_name}"
                if with_name not in result.artists:
                    result.artists.append(with_name)
            # Apply live_event
            if live_event:
                result.live_event = live_event
            return result

    return None


# =============================================================================
# Cover patterns
# =============================================================================

def _c1(title: str, channel_artist: str) -> ParseResult | None:
    """C1: 【歌ってみた】「<曲> ⧸ <原曲者>」covered by <歌手>"""
    m = re.match(
        r"【歌ってみた】「(.+?)\s*⧸\s*(.+?)」\s*covered\s+by\s+(.+)",
        title, re.IGNORECASE,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    original = _strip(m.group(2))
    performer = _strip(m.group(3))
    artists = _split_artists(performer)
    return ParseResult(
        title=f"{song} (Cover)",
        artists=artists,
        is_cover=True,
        original_artist=original,
        pattern_id="C1",
    )


def _c2(title: str, channel_artist: str) -> ParseResult | None:
    """C2: 【歌ってみた】<曲> ⧸ covered by <歌手>"""
    m = re.match(
        r"【歌ってみた】(.+?)\s*⧸\s*covered\s+by\s+(.+)",
        title, re.IGNORECASE,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    performer = _strip(m.group(2))
    # Handle "ヰ世界情緒 × 花譜" style
    artists = _split_artists(performer)
    return ParseResult(
        title=f"{song} (Cover)",
        artists=artists,
        is_cover=True,
        pattern_id="C2",
    )


def _c5(title: str, channel_artist: str) -> ParseResult | None:
    """C5: 【歌ってみた】<曲> - <原曲者> covered by <歌手>"""
    m = re.match(
        r"【歌ってみた】(.+?)\s*-\s*(.+?)\s+covered\s+by\s+(.+)",
        title, re.IGNORECASE,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    original = _strip(m.group(2))
    performer = _strip(m.group(3))
    artists = _split_artists(performer)
    return ParseResult(
        title=f"{song} (Cover)",
        artists=artists,
        is_cover=True,
        original_artist=original,
        pattern_id="C5",
    )


def _c6(title: str, channel_artist: str) -> ParseResult | None:
    """C6: <曲> - <原曲者> Covered by <歌手> ⧸ <英名>"""
    m = re.match(
        r"(.+?)\s*-\s*(.+?)\s+Covered\s+by\s+(.+?)\s*⧸\s*(.+)",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    original = _strip(m.group(2))
    performer_jp = _strip(m.group(3))
    # performer_jp may include "feat. <name>"
    performer_jp, feat_name = _parse_feat(performer_jp)
    artists = _split_artists(performer_jp)
    if feat_name:
        artists.append(feat_name)
    return ParseResult(
        title=f"{song} (Cover)" if not feat_name else f"{song} feat. {feat_name} (Cover)",
        artists=artists,
        is_cover=True,
        original_artist=original,
        pattern_id="C6",
    )


def _c7(title: str, channel_artist: str) -> ParseResult | None:
    """C7: HIMEHINA『<曲>』Cover"""
    m = re.match(
        r"HIMEHINA『(.+?)』Cover\s*$",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    return ParseResult(
        title=f"{song} (Cover)",
        artists=["HIMEHINA"],
        is_cover=True,
        pattern_id="C7",
    )


def _c3(title: str, channel_artist: str) -> ParseResult | None:
    """C3: 【歌ってみた】<曲> by <歌手>"""
    m = re.match(
        r"【歌ってみた】(.+?)\s+by\s+(.+?)(?:\s*$)",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    performer = _strip(m.group(2))
    artists = _split_artists(performer)
    return ParseResult(
        title=f"{song} (Cover)",
        artists=artists,
        is_cover=True,
        pattern_id="C3",
    )


def _c4(title: str, channel_artist: str) -> ParseResult | None:
    """C4: 【歌ってみた】<曲> Covered by <歌手>【...】"""
    m = re.match(
        r"【歌ってみた】(.+?)\s+Covered\s+by\s+(.+?)(?:【.+?】)*\s*$",
        title, re.IGNORECASE,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    performer = _strip(m.group(2))
    # Handle "RARA & VITTE" or "CHINO & RARA" style
    artists = re.split(r"\s*&\s*", performer)
    artists = [_strip(a) for a in artists if _strip(a)]
    return ParseResult(
        title=f"{song} (Cover)",
        artists=artists,
        is_cover=True,
        pattern_id="C4",
    )


# =============================================================================
# Original patterns
# =============================================================================

def _o3(title: str, channel_artist: str) -> ParseResult | None:
    """O3: 【組曲N】<歌手> #<番号> 「<曲>」【オリジナルMV】"""
    m = re.match(
        r"【組曲\d+】(.+?)\s*#\s*(\d+)\s*「(.+?)」\s*【オリジナルMV】\s*$",
        title,
    )
    if not m:
        return None
    performer = _strip(m.group(1))
    song = _strip(m.group(3))
    song, feat_name = _parse_feat(song)
    artists = _split_artists(performer)
    if feat_name:
        if feat_name not in artists:
            artists.append(feat_name)
        display_title = f"{song} feat. {feat_name}"
    else:
        display_title = song
    return ParseResult(
        title=display_title,
        artists=artists,
        pattern_id="O3",
    )


def _o1(title: str, channel_artist: str) -> ParseResult | None:
    """O1: <歌手> #<番号>「<曲>」【オリジナルMV】
    Also handles: <歌手> # <番号>「<曲>」【オリジナルMV】"""
    m = re.match(
        r"(.+?)\s*#\s*(\d+)\s*「(.+?)」\s*【オリジナルMV】\s*$",
        title,
    )
    if not m:
        return None
    performer = _strip(m.group(1))
    song = _strip(m.group(3))
    song, feat_name = _parse_feat(song)
    artists = _split_artists(performer)
    if feat_name:
        if feat_name not in artists:
            artists.append(feat_name)
        display_title = f"{song} feat. {feat_name}"
    else:
        display_title = song
    return ParseResult(
        title=display_title,
        artists=artists,
        pattern_id="O1",
    )


def _o5(title: str, channel_artist: str) -> ParseResult | None:
    """O5: No.<番号>　<歌手> -<英名>- 「<曲>」【...】"""
    m = re.match(
        r"No\.(\d+)\s+(.+?)\s+-\w+-\s+「(.+?)」\s*【.+?】\s*$",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(3))
    artists = [channel_artist]
    return ParseResult(
        title=song,
        artists=artists,
        pattern_id="O5",
    )


def _o6(title: str, channel_artist: str) -> ParseResult | None:
    """O6: 【ソロオリジナルMV】VALIS − <番号>「<曲>」by <歌手>【...】"""
    m = re.match(
        r"【ソロオリジナルMV】VALIS\s*[−\-]\s*(\d+)「(.+?)」\s*by\s+(.+?)【.+?】\s*$",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(2))
    performer = _strip(m.group(3))
    return ParseResult(
        title=song,
        artists=[performer],
        pattern_id="O6",
    )


def _o7(title: str, channel_artist: str) -> ParseResult | None:
    """O7: 【オリジナルMV】VALIS − <番号>「<曲>」【合唱】"""
    m = re.match(
        r"【オリジナルMV】VALIS\s*[−\-]\s*(\d+)「(.+?)」\s*【合唱】\s*$",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(2))
    return ParseResult(
        title=song,
        artists=list(VALIS_MEMBERS),
        pattern_id="O7",
    )


def _o8(title: str, channel_artist: str) -> ParseResult | None:
    """O8: HIMEHINA『<曲>』MV #<タグ>"""
    m = re.match(
        r"HIMEHINA『(.+?)』MV\s+#(.+?)\s*$",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    return ParseResult(
        title=song,
        artists=["HIMEHINA"],
        pattern_id="O8",
    )


def _o9(title: str, channel_artist: str) -> ParseResult | None:
    """O9: <歌手> - <曲> ⧸ <英名> - <英曲名>
    Also handles: <歌手> - <曲> ⧸ <英名> - <英曲名> (Official Music Video)"""
    m = re.match(
        r"(.+?)\s+-\s+(.+?)\s*⧸\s*(.+?)(?:\s*\(Official Music Video\))?\s*$",
        title,
    )
    if not m:
        return None
    performer = _strip(m.group(1))
    song = _strip(m.group(2))
    artists = _split_artists(performer)
    return ParseResult(
        title=song,
        artists=artists,
        pattern_id="O9",
    )


# =============================================================================
# Live and special patterns
# =============================================================================

def _l1(title: str, channel_artist: str) -> ParseResult | None:
    """L1: 【VALIS】<曲> #<イベント> Live ver.【...】"""
    m = re.match(
        r"【VALIS】(.+?)\s+#(.+?)\s+Live\s+ver\.\s*【(.+?)】\s*$",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    event = _strip(m.group(2))
    display_title = f"{song} \u3010{event} Live ver.\u3011"
    return ParseResult(
        title=display_title,
        artists=list(VALIS_MEMBERS),
        is_live=True,
        live_event=event,
        pattern_id="L1",
    )


def _c8(title: str, channel_artist: str) -> ParseResult | None:
    """C8: <曲> (Rearranged Ver.) - <歌手> ⧸ <英名>"""
    m = re.match(
        r"(.+?)\s+\(Rearranged\s+[Vv]er\.?\)\s*-\s*(.+?)\s*⧸\s*(.+)",
        title,
    )
    if not m:
        return None
    song = _strip(m.group(1))
    performer = _strip(m.group(2))
    artists = _split_artists(performer)
    return ParseResult(
        title=f"{song} (Rearranged Ver.)",
        artists=artists,
        pattern_id="C8",
    )


def _o1_rearranged(title: str, channel_artist: str) -> ParseResult | None:
    """O1-R: <歌手> #<番号>「<曲>(Rearranged ver.)」【オリジナルMV】"""
    m = re.match(
        r"(.+?)\s*#\s*(\d+)\s*「(.+?)\s*\(Rearranged\s+ver\.?\)」\s*【オリジナルMV】\s*$",
        title, re.IGNORECASE,
    )
    if not m:
        return None
    performer = _strip(m.group(1))
    song = _strip(m.group(3))
    artists = _split_artists(performer)
    return ParseResult(
        title=f"{song} (Rearranged Ver.)",
        artists=artists,
        pattern_id="O1-R",
    )


# Pattern priority order
_PATTERNS = [
    _c1,   # 【歌ってみた】「<曲> ⧸ <原曲者>」covered by ...
    _c2,   # 【歌ってみた】<曲> ⧸ covered by ...
    _c5,   # 【歌ってみた】<曲> - <原曲者> covered by ...
    _c6,   # <曲> - <原曲者> Covered by <歌手> ⧸ ...
    _c7,   # HIMEHINA『<曲>』Cover
    _c4,   # 【歌ってみた】<曲> Covered by <歌手>【...】
    _c3,   # 【歌ってみた】<曲> by <歌手>
    _o3,   # 【組曲N】<歌手> #<番号> 「<曲>」【オリジナルMV】
    _o1_rearranged,  # <歌手> #<番号>「<曲>(Rearranged ver.)」【オリジナルMV】
    _o1,   # <歌手> #<番号>「<曲>」【オリジナルMV】
    _o5,   # No.<番号>　<歌手> -<英名>- 「<曲>」【...】
    _o6,   # 【ソロオリジナルMV】VALIS − <番号>「<曲>」by <歌手>【...】
    _o7,   # 【オリジナルMV】VALIS − <番号>「<曲>」【合唱】
    _o8,   # HIMEHINA『<曲>』MV #<タグ>
    _l1,   # 【VALIS】<曲> #<イベント> Live ver.【...】
    _c8,   # <曲> (Rearranged Ver.) - <歌手> ⧸ ...
    _o9,   # <歌手> - <曲> ⧸ <英名> - <英曲名>
]


# =============================================================================
# Parse failure diagnosis
# =============================================================================

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "cover": [
        "歌ってみた", "covered by", "Covered by", "Cover", "cover",
        "カバー",
    ],
    "original": [
        "オリジナルMV", "Official Music Video", "Official Lyric Video",
        "オリジナル曲", "Original",
    ],
    "live": [
        "Live ver.", "LIVE Video", "Live", "ライブ",
    ],
}

_PATTERN_SUMMARIES: list[tuple[str, str]] = [
    ("C1", "【歌ってみた】「<曲> ⧸ <原曲者>」covered by <歌手>"),
    ("C2", "【歌ってみた】<曲> ⧸ covered by <歌手>"),
    ("C5", "【歌ってみた】<曲> - <原曲者> covered by <歌手>"),
    ("C6", "<曲> - <原曲者> Covered by <歌手> ⧸ <英名>"),
    ("C7", "HIMEHINA『<曲>』Cover"),
    ("C4", "【歌ってみた】<曲> Covered by <歌手>【...】"),
    ("C3", "【歌ってみた】<曲> by <歌手>"),
    ("C8", "<曲> (Rearranged Ver.) - <歌手> ⧸ <英名>"),
    ("O3", "【組曲N】<歌手> #<番号> 「<曲>」【オリジナルMV】"),
    ("O1-R", "<歌手> #<番号>「<曲>(Rearranged ver.)」【オリジナルMV】"),
    ("O1", "<歌手> #<番号>「<曲>」【オリジナルMV】"),
    ("O5", "No.<番号>　<歌手> -<英名>- 「<曲>」【...】"),
    ("O6", "【ソロオリジナルMV】VALIS − <番号>「<曲>」by <歌手>【...】"),
    ("O7", "【オリジナルMV】VALIS − <番号>「<曲>」【合唱】"),
    ("O8", "HIMEHINA『<曲>』MV #<タグ>"),
    ("O9", "<歌手> - <曲> ⧸ <英名> - <英曲名>"),
    ("L1", "【VALIS】<曲> #<イベント> Live ver.【...】"),
]

_STRUCTURAL_FEATURES: list[tuple[str, str]] = [
    (r"「.*?」", "「」brackets"),
    (r"『.*?』", "『』brackets"),
    (r"【.*?】", "【】brackets"),
    (r"⧸", "⧸ separator"),
    (r"#\s*\d+", "#number"),
    (r"No\.\d+", "No.number"),
    (r"×", "× joint"),
    (r"\(from\s+.+\)", "(from ...) suffix"),
    (r"\bwith\s+\S+", "with <name>"),
    (r"\bfeat\.\s*\S+", "feat. <name>"),
]


@dataclass
class ParseDiagnosis:
    """Diagnosis information for a parse failure."""

    raw_title: str
    channel_dir: str
    channel_artist: str
    likely_category: str  # "cover", "original", "live", or "unknown"
    detected_keywords: list[str] = field(default_factory=list)
    structural_features: list[str] = field(default_factory=list)
    claude_prompt: str = ""


def diagnose_parse_failure(
    raw_title: str,
    channel_dir: str,
    channel_artist: str,
) -> ParseDiagnosis:
    """Analyze a title that failed to match any pattern and produce diagnostic info.

    Returns a ParseDiagnosis with category estimation and a Claude-ready prompt.
    """
    title = _nfc(raw_title.strip())

    # Detect category keywords
    detected_keywords: list[str] = []
    likely_category = "unknown"
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title:
                detected_keywords.append(kw)
                if likely_category == "unknown":
                    likely_category = category

    # Detect structural features
    structural_features: list[str] = []
    for pattern, label in _STRUCTURAL_FEATURES:
        if re.search(pattern, title):
            structural_features.append(label)

    # Build Claude prompt
    patterns_list = "\n".join(
        f"  {pid}: {desc}" for pid, desc in _PATTERN_SUMMARIES
    )

    features_info = ""
    if detected_keywords:
        features_info += f"  検出キーワード: {', '.join(detected_keywords)}\n"
    if structural_features:
        features_info += f"  構造的特徴: {', '.join(structural_features)}\n"

    claude_prompt = (
        "ytmusic の parser.py に新しいパターンを追加してください。\n"
        "\n"
        "以下のタイトルがどのパターンにもマッチしませんでした:\n"
        "\n"
        f"  タイトル: {title}\n"
        f"  チャンネル: {channel_dir}\n"
        f"  チャンネルアーティスト: {channel_artist}\n"
        f"  推定カテゴリ: {likely_category}\n"
        f"{features_info}"
        "\n"
        "既存パターン一覧:\n"
        f"{patterns_list}\n"
        "\n"
        "このタイトルにマッチする新しいパターン関数を _PATTERNS リストの適切な位置に追加し、\n"
        "tests/test_parser.py に対応するテストケースも追加してください。\n"
        "既存パターンとの干渉に注意し、パターンの優先順位を考慮してください。"
    )

    return ParseDiagnosis(
        raw_title=raw_title,
        channel_dir=channel_dir,
        channel_artist=channel_artist,
        likely_category=likely_category,
        detected_keywords=detected_keywords,
        structural_features=structural_features,
        claude_prompt=claude_prompt,
    )
