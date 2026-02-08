"""Parameterized tests for all downloaded file title patterns."""

import pytest

from ytmusic.parser import parse_title

# (raw_title, channel_artist, expected_title, expected_artists, expected_pattern_id)
CASES = [
    # === 春猿火 ⧸ Harusaruhi ===
    # O1: <歌手> # <番号>「<曲>」【オリジナルMV】
    (
        "春猿火 # 58「YONA YONA feat. Rin音」【オリジナルMV】",
        "春猿火",
        "YONA YONA feat. Rin音",
        ["春猿火", "Rin音"],
        "O1",
    ),
    # C1: 【歌ってみた】「<曲> ⧸ <原曲者>」covered by <歌手>
    (
        "【歌ってみた】「ピッカーン！ ⧸ Giga & TeddyLoid meets 松田里奈 & 森田ひかる (櫻坂46)」covered by 春猿火",
        "春猿火",
        "ピッカーン！ (Cover)",
        ["春猿火"],
        "C1",
    ),
    (
        "【歌ってみた】「喰らいながら ⧸ 獅子志司」covered by 春猿火",
        "春猿火",
        "喰らいながら (Cover)",
        ["春猿火"],
        "C1",
    ),
    (
        "【歌ってみた】「拝啓ドッペルゲンガー ⧸ kemu」covered by 春猿火",
        "春猿火",
        "拝啓ドッペルゲンガー (Cover)",
        ["春猿火"],
        "C1",
    ),
    (
        "【歌ってみた】「Diver ⧸ NICO Touches the Walls」covered by 春猿火",
        "春猿火",
        "Diver (Cover)",
        ["春猿火"],
        "C1",
    ),
    (
        "【歌ってみた】「不器用な男 ⧸ カンザキイオリ」covered by 春猿火",
        "春猿火",
        "不器用な男 (Cover)",
        ["春猿火"],
        "C1",
    ),
    # C1 with 'with <name>' (pre-processed) and (from ...)
    (
        "【歌ってみた】「チルドレンレコード ⧸ じん」 covered by 春猿火 with 梓川 (from CREAM PUFF LIVE 4 2025.7.21)",
        "春猿火",
        "チルドレンレコード (Cover) with 梓川",
        ["春猿火", "梓川"],
        "C1",
    ),
    # C1 with (from ...)
    (
        "【歌ってみた】「カワルミライ ⧸ Choucho」covered by 春猿火 (from CREAM PUFF LIVE 4 2025.7.21)",
        "春猿火",
        "カワルミライ (Cover)",
        ["春猿火"],
        "C1",
    ),
    # O1 more
    (
        "春猿火 # 59「距離。」【オリジナルMV】",
        "春猿火",
        "距離。",
        ["春猿火"],
        "O1",
    ),
    # C1 with fullwidth chars in original artist
    (
        "【歌ってみた】「ゴーストルール⧸DECO＊27」covered by 春猿火",
        "春猿火",
        "ゴーストルール (Cover)",
        ["春猿火"],
        "C1",
    ),
    (
        "【歌ってみた】「ロスタイムメモリー ⧸ じん」covered by 春猿火",
        "春猿火",
        "ロスタイムメモリー (Cover)",
        ["春猿火"],
        "C1",
    ),
    (
        "春猿火 # 60「(A)letheia」【オリジナルMV】",
        "春猿火",
        "(A)letheia",
        ["春猿火"],
        "O1",
    ),
    (
        "【歌ってみた】「エゴイスト ⧸ 大沼パセリ」covered by 春猿火",
        "春猿火",
        "エゴイスト (Cover)",
        ["春猿火"],
        "C1",
    ),

    # === 幸祜 - KOKO - ===
    # O5: No.<番号>　<歌手> -<英名>- 「<曲>」【...】
    (
        "No.038　幸祜 -KOKO- 「オレンジ」【Official Lyric Video】",
        "KOKO",
        "オレンジ",
        ["KOKO"],
        "O5",
    ),
    (
        "No.039　幸祜 -KOKO- 「ANTINOMY」【LIVE Video from 3rd ONE-MAN LIVE「PLAYERⅢ」】",
        "KOKO",
        "ANTINOMY",
        ["KOKO"],
        "O5",
    ),
    (
        "No.040　幸祜 -KOKO- 「ミラージュコード」【LIVE Video from 3rd ONE-MAN LIVE「PLAYERⅢ」】",
        "KOKO",
        "ミラージュコード",
        ["KOKO"],
        "O5",
    ),
    (
        "No.041　幸祜 -KOKO- 「在処」【Official Music Video】",
        "KOKO",
        "在処",
        ["KOKO"],
        "O5",
    ),
    (
        "No.042　幸祜 -KOKO- 「Kazura」【Official Music Video】",
        "KOKO",
        "Kazura",
        ["KOKO"],
        "O5",
    ),
    # C2: 【歌ってみた】<曲> ⧸ covered by <歌手>
    (
        "【歌ってみた】右肩の蝶 ⧸ covered by 幸祜",
        "KOKO",
        "右肩の蝶 (Cover)",
        ["幸祜"],
        "C2",
    ),
    (
        "No.043　幸祜 -KOKO- 「シャングリラ」【Official Music Video】",
        "KOKO",
        "シャングリラ",
        ["KOKO"],
        "O5",
    ),
    (
        "【歌ってみた】CR詠ZY ⧸ covered by 幸祜",
        "KOKO",
        "CR詠ZY (Cover)",
        ["幸祜"],
        "C2",
    ),

    # === 明透 -ᴀsᴜ- ===
    # O9: <歌手> - <曲> ⧸ <英名> - <英曲名>
    (
        "明透 - Link ⧸ ASU - Link",
        "明透",
        "Link",
        ["明透"],
        "O9",
    ),
    # C5: 【歌ってみた】<曲> - <原曲者> covered by <歌手>
    (
        "【歌ってみた】Plazma - 米津玄師 covered by 明透",
        "明透",
        "Plazma (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】睨めっ娘 - 友成空 covered by 明透",
        "明透",
        "睨めっ娘 (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】UNDEAD - YOASOBI covered by 明透",
        "明透",
        "UNDEAD (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】Super Ball - TOMOO covered by 明透",
        "明透",
        "Super Ball (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】BRAIN - Kanaria covered by 明透",
        "明透",
        "BRAIN (Cover)",
        ["明透"],
        "C5",
    ),
    # C5 with × in performer (two people)
    (
        "【歌ってみた】二時間だけのバカンスfeaturing 椎名林檎 -宇多田ヒカル covered by 明透×琶舞",
        "明透",
        "二時間だけのバカンスfeaturing 椎名林檎 (Cover)",
        ["明透", "琶舞"],
        "C5",
    ),
    (
        "【歌ってみた】DRESSING ROOM -なとり covered by 明透",
        "明透",
        "DRESSING ROOM (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】徘徊 - AKASAKI covered by 明透",
        "明透",
        "徘徊 (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】[A]ddiction - GigaReol×EVO+ covered by 明透",
        "明透",
        "[A]ddiction (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】群青 - YOASOBI covered by 明透",
        "明透",
        "群青 (Cover)",
        ["明透"],
        "C5",
    ),
    (
        "【歌ってみた】幾億光年 - omoinotake covered by 明透",
        "明透",
        "幾億光年 (Cover)",
        ["明透"],
        "C5",
    ),
    # O9 with (Official Music Video) suffix
    (
        "明透 - HOME ⧸ ASU - HOME (Official Music Video)",
        "明透",
        "HOME",
        ["明透"],
        "O9",
    ),
    (
        "【歌ってみた】プロポーズ - なとり covered by 明透",
        "明透",
        "プロポーズ (Cover)",
        ["明透"],
        "C5",
    ),

    # === ヰ世界情緒 -Isekaijoucho- ===
    # C2
    (
        "【歌ってみた】モエチャッカファイア ⧸ covered by ヰ世界情緒",
        "ヰ世界情緒",
        "モエチャッカファイア (Cover)",
        ["ヰ世界情緒"],
        "C2",
    ),
    (
        "【歌ってみた】終着 ⧸ covered by ヰ世界情緒",
        "ヰ世界情緒",
        "終着 (Cover)",
        ["ヰ世界情緒"],
        "C2",
    ),
    (
        "【歌ってみた】甘き心中はプールサイドで ⧸ covered by ヰ世界情緒",
        "ヰ世界情緒",
        "甘き心中はプールサイドで (Cover)",
        ["ヰ世界情緒"],
        "C2",
    ),
    # O1
    (
        "ヰ世界情緒 #58「ETERNAL」【オリジナルMV】",
        "ヰ世界情緒",
        "ETERNAL",
        ["ヰ世界情緒"],
        "O1",
    ),
    (
        "【歌ってみた】isomers ⧸ covered by ヰ世界情緒",
        "ヰ世界情緒",
        "isomers (Cover)",
        ["ヰ世界情緒"],
        "C2",
    ),
    (
        "ヰ世界情緒 #59「BREATHE」【オリジナルMV】",
        "ヰ世界情緒",
        "BREATHE",
        ["ヰ世界情緒"],
        "O1",
    ),
    (
        "【歌ってみた】エス ⧸ covered by ヰ世界情緒",
        "ヰ世界情緒",
        "エス (Cover)",
        ["ヰ世界情緒"],
        "C2",
    ),
    # C2 with × in performer
    (
        "【歌ってみた】天天天国地獄国 ⧸ covered by ヰ世界情緒 × 花譜",
        "ヰ世界情緒",
        "天天天国地獄国 (Cover)",
        ["ヰ世界情緒", "花譜"],
        "C2",
    ),
    # O1-R: rearranged ver in O1 format
    (
        "ヰ世界情緒 × 春猿火 #60「BREATHE(Rearranged ver.)」【オリジナルMV】",
        "ヰ世界情緒",
        "BREATHE (Rearranged Ver.)",
        ["ヰ世界情緒", "春猿火"],
        "O1-R",
    ),

    # === HIMEHINA Channel ===
    # C7
    (
        "HIMEHINA『UNDEAD』Cover",
        "HIMEHINA",
        "UNDEAD (Cover)",
        ["HIMEHINA"],
        "C7",
    ),
    # O8
    (
        "HIMEHINA『V』MV #ヴィー",
        "HIMEHINA",
        "V",
        ["HIMEHINA"],
        "O8",
    ),
    (
        "HIMEHINA『バブリン』MV #バブリン",
        "HIMEHINA",
        "バブリン",
        ["HIMEHINA"],
        "O8",
    ),

    # === KAF ===
    # C3: 【歌ってみた】<曲> by <歌手>
    (
        "【歌ってみた】1ピース by 花譜",
        "花譜",
        "1ピース (Cover)",
        ["花譜"],
        "C3",
    ),
    (
        "【歌ってみた】水死体は恋したい by 花譜",
        "花譜",
        "水死体は恋したい (Cover)",
        ["花譜"],
        "C3",
    ),
    (
        "【歌ってみた】おへんぢください by 花譜",
        "花譜",
        "おへんぢください (Cover)",
        ["花譜"],
        "C3",
    ),
    # O3: 【組曲N】<歌手> #<番号> 「<曲>」【オリジナルMV】
    (
        "【組曲2】花譜×CHiCO #150 「撃って」【オリジナルMV】",
        "花譜",
        "撃って",
        ["花譜", "CHiCO"],
        "O3",
    ),
    (
        "【歌ってみた】こころのたまご by 花譜",
        "花譜",
        "こころのたまご (Cover)",
        ["花譜"],
        "C3",
    ),
    (
        "【歌ってみた】hp by 花譜",
        "花譜",
        "hp (Cover)",
        ["花譜"],
        "C3",
    ),
    (
        "【歌ってみた】Hey phone by 花譜",
        "花譜",
        "Hey phone (Cover)",
        ["花譜"],
        "C3",
    ),
    # O1
    (
        "花譜 #152 「ひとえに壊れて」【オリジナルMV】",
        "花譜",
        "ひとえに壊れて",
        ["花譜"],
        "O1",
    ),
    # C3 with × in performer
    (
        "【歌ってみた】愛×愛ホイッスル by 花譜×ヰ世界情緒",
        "花譜",
        "愛×愛ホイッスル (Cover)",
        ["花譜", "ヰ世界情緒"],
        "C3",
    ),
    # O3
    (
        "【組曲2】花譜×Mori Calliope #153 「光」【オリジナルMV】",
        "花譜",
        "光",
        ["花譜", "Mori Calliope"],
        "O3",
    ),
    (
        "【歌ってみた】わたしは禁忌 by 花譜",
        "花譜",
        "わたしは禁忌 (Cover)",
        ["花譜"],
        "C3",
    ),

    # === RIM ===
    # C6: <曲> - <原曲者> Covered by <歌手> ⧸ <英名>
    (
        "stay tune - 7co Covered by 理芽 ⧸ RIM",
        "理芽",
        "stay tune (Cover)",
        ["理芽"],
        "C6",
    ),
    (
        "The End of the F＊＊＊ing World - ブランデー戦記 Covered by 理芽 ⧸ RIM",
        "理芽",
        "The End of the F＊＊＊ing World (Cover)",
        ["理芽"],
        "C6",
    ),
    (
        "HALVES - 嫌々 Covered by 理芽 ⧸ RIM",
        "理芽",
        "HALVES (Cover)",
        ["理芽"],
        "C6",
    ),
    (
        "ほろよい - Sanghee ⧸ さんひ  Covered by 理芽 ⧸ RIM",
        "理芽",
        "ほろよい (Cover)",
        ["理芽"],
        "C6",
    ),
    (
        "おしゃかしゃま - RADWIMPS Covered by 理芽 ⧸ RIM",
        "理芽",
        "おしゃかしゃま (Cover)",
        ["理芽"],
        "C6",
    ),
    (
        "指髪 - チョーキューメイ Covered by 理芽 ⧸ RIM",
        "理芽",
        "指髪 (Cover)",
        ["理芽"],
        "C6",
    ),
    # O9: <歌手> - <曲> ⧸ <英名> - <英曲名>
    (
        "理芽 - 閃光だった ⧸ RIM - INSIGHT",
        "理芽",
        "閃光だった",
        ["理芽"],
        "O9",
    ),
    # C6 with feat.
    (
        "長く短い祭 - 椎名林檎 Covered by 理芽 feat. 梓川 ⧸ RIM feat. Azsagawa",
        "理芽",
        "長く短い祭 feat. 梓川 (Cover)",
        ["理芽", "梓川"],
        "C6",
    ),
    (
        "ひこうき雲 - 荒井由実 Covered by 理芽 ⧸ RIM",
        "理芽",
        "ひこうき雲 (Cover)",
        ["理芽"],
        "C6",
    ),
    # C8: <曲> (Rearranged Ver.) - <歌手> ⧸ <英名>
    (
        "閃光だった (Rearranged Ver.) - 理芽×幸祜 ⧸ RIM & KOKO",
        "理芽",
        "閃光だった (Rearranged Ver.)",
        ["理芽", "幸祜"],
        "C8",
    ),
    (
        "四季ノ唄 - MINMI Covered by 理芽 ⧸ RIM",
        "理芽",
        "四季ノ唄 (Cover)",
        ["理芽"],
        "C6",
    ),

    # === VALIS ===
    # O6: 【ソロオリジナルMV】VALIS − <番号>「<曲>」by <歌手>【...】
    (
        "【ソロオリジナルMV】VALIS − 008「βlack Swan」by VITTE【VALIS独唱】",
        "VALIS",
        "βlack Swan",
        ["VITTE"],
        "O6",
    ),
    (
        "【ソロオリジナルMV】VALIS − 009「Mute Beat」by MYU【VALIS独唱】",
        "VALIS",
        "Mute Beat",
        ["MYU"],
        "O6",
    ),
    (
        "【ソロオリジナルMV】VALIS − 010「Eyes On Me」by NEFFY【VALIS独唱】",
        "VALIS",
        "Eyes On Me",
        ["NEFFY"],
        "O6",
    ),
    (
        "【ソロオリジナルMV】VALIS − 011「JUICE」by RARA【VALIS独唱】",
        "VALIS",
        "JUICE",
        ["RARA"],
        "O6",
    ),
    # O7: 【オリジナルMV】VALIS − <番号>「<曲>」【合唱】
    (
        "【オリジナルMV】VALIS − 035「共振ハートビート」【合唱】",
        "VALIS",
        "共振ハートビート",
        ["VALIS", "CHINO", "MYU", "NEFFY", "NINA", "RARA", "VITTE"],
        "O7",
    ),
    # C4: 【歌ってみた】<曲> Covered by <歌手>【...】
    (
        "【歌ってみた】また旅はネコミミと Covered by RARA & VITTE【二重唱】",
        "VALIS",
        "また旅はネコミミと (Cover)",
        ["RARA", "VITTE"],
        "C4",
    ),
    # L1: 【VALIS】<曲> #<イベント> Live ver.【...】
    (
        "【VALIS】純情エトワール #喝采カーテンコール Live ver.【Act.2】",
        "VALIS",
        "純情エトワール 【喝采カーテンコール Live ver.】",
        ["VALIS", "CHINO", "MYU", "NEFFY", "NINA", "RARA", "VITTE"],
        "L1",
    ),
    # C4
    (
        "【歌ってみた】レオ Covered by NEFFY【独唱】",
        "VALIS",
        "レオ (Cover)",
        ["NEFFY"],
        "C4",
    ),
    (
        "【歌ってみた】ツキヨミ Covered by CHINO【独唱】",
        "VALIS",
        "ツキヨミ (Cover)",
        ["CHINO"],
        "C4",
    ),
    (
        "【歌ってみた】可惜夜 Covered by MYU【独唱】",
        "VALIS",
        "可惜夜 (Cover)",
        ["MYU"],
        "C4",
    ),
    (
        "【歌ってみた】眼裏の懐疑 Covered by CHINO & RARA【二重唱】",
        "VALIS",
        "眼裏の懐疑 (Cover)",
        ["CHINO", "RARA"],
        "C4",
    ),
    # L1
    (
        "【VALIS】黄昏シミュレイド #喝采カーテンコール Live ver.【Act.2】",
        "VALIS",
        "黄昏シミュレイド 【喝采カーテンコール Live ver.】",
        ["VALIS", "CHINO", "MYU", "NEFFY", "NINA", "RARA", "VITTE"],
        "L1",
    ),
    (
        "【歌ってみた】生きるよすが Covered by RARA【独唱】",
        "VALIS",
        "生きるよすが (Cover)",
        ["RARA"],
        "C4",
    ),
    # O7
    (
        "【オリジナルMV】VALIS − 036「廻転コースター」【合唱】",
        "VALIS",
        "廻転コースター",
        ["VALIS", "CHINO", "MYU", "NEFFY", "NINA", "RARA", "VITTE"],
        "O7",
    ),
]


@pytest.mark.parametrize(
    "raw_title,channel_artist,expected_title,expected_artists,expected_pattern_id",
    CASES,
    ids=[f"{c[4]}:{c[0][:40]}" for c in CASES],
)
def test_parse_title(
    raw_title: str,
    channel_artist: str,
    expected_title: str,
    expected_artists: list[str],
    expected_pattern_id: str,
) -> None:
    result = parse_title(raw_title, channel_artist)
    assert result is not None, f"No pattern matched for: {raw_title}"
    assert result.title == expected_title, f"Title mismatch for: {raw_title}"
    assert result.artists == expected_artists, f"Artists mismatch for: {raw_title}"
    assert result.pattern_id == expected_pattern_id, f"Pattern mismatch for: {raw_title}"
