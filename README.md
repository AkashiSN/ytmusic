# ytmusic

YouTube歌ってみた動画の音声をダウンロードし、メタデータ付与・ライブラリ配置までを自動化するCLIツール。

foobar2000での手動作業（アートワーク埋め込み、メタデータ設定、R128ゲイン計算、リネーム・移動）を置き換え、yt-dlpでダウンロードしたファイルからSMBライブラリへの配置までをワンコマンドで処理する。

## インストール

```bash
# uv (推奨)
uv tool install -e .

# pip
pip install -e .
```

### 設定ファイルの配置

```bash
# サンプルをコピーして編集
mkdir -p ~/.config/ytmusic
cp config.toml.example ~/.config/ytmusic/config.toml
vi ~/.config/ytmusic/config.toml
```

### 外部ツール

| ツール | 用途 | インストール |
|--------|------|-------------|
| ffmpeg | Opus抽出、R128ゲイン計算 | `brew install ffmpeg` |
| AtomicParsley | m4aからアートワーク抽出 | [GitHub Releases](https://github.com/wez/atomicparsley/releases) |
| yt-dlp | YouTube動画ダウンロード | `brew install yt-dlp` |

## 使い方

### ダウンロード

```bash
# 単一URL
ytmusic download https://www.youtube.com/watch?v=XXXXX

# 複数URL一括（1行1URL）
ytmusic download --urls urls.txt

# Chrome UAを自動検出して config.toml に書き込み
ytmusic update-ua
```

### 処理

```bash
# 未処理ファイル一覧
ytmusic scan

# プレビュー（実際のファイル操作なし）
ytmusic process --dry-run

# 全自動処理
ytmusic process

# 特定チャンネルのみ
ytmusic process --channel KAF

# 対話的処理（各トラック確認）
ytmusic process --channel KAF -i
```

### パーステスト

```bash
ytmusic parse "【歌ってみた】1ピース by 花譜" --channel KAF
# Pattern:  C3
# Title:    1ピース (Cover)
# Artists:  ['花譜']
# Cover:    True
```

## 処理パイプライン

```
~/Music/Youtube/<channel>/<epoch>-<title>.{webm,m4a}
  │
  ├─ DISCOVER   webm+m4aペアを走査
  ├─ PARSE      正規表現でタイトルからメタデータ抽出
  ├─ EXTRACT    ffmpeg -c:a copy: webm → Opus
  ├─ ARTWORK    AtomicParsley: m4a → アートワーク画像抽出
  ├─ R128       ffmpeg loudnorm → R128_TRACK_GAIN (Q7.8形式)
  ├─ TAG        mutagen: TITLE, ARTIST, ALBUM, ALBUMARTIST, TRACKNUMBER,
  │             R128_TRACK_GAIN, METADATA_BLOCK_PICTURE
  └─ ORGANIZE   ファイルを最終パスへ配置:
                 Opus(タグ付) → /Volumes/musics/Opus/<Cat>/<Artist>/<Album>/
                 Opus(コピー) → /Volumes/musics/Original/<Cat>/<Artist>/<Album>/Opus/
                 webm         → /Volumes/musics/Original/<Cat>/<Artist>/<Album>/Original/
```

## 設定ファイル

以下の優先度で `config.toml` を検索する:

1. `--config` / `-c` フラグで指定したパス
2. 環境変数 `YTMUSIC_CONFIG` で指定したパス
3. `~/.config/ytmusic/config.toml` (デフォルト)

```bash
# 環境変数で指定する場合
export YTMUSIC_CONFIG=~/my-ytmusic-config.toml

# CLI フラグで指定する場合
ytmusic -c /path/to/config.toml process --dry-run
```

### 設定項目

```toml
[paths]
youtube_dir = "~/Music/Youtube"
library_dir = "/Volumes/musics"

[tools]
ffmpeg = "ffmpeg"
atomicparsley = "~/.local/bin/AtomicParsley"
yt-dlp = "yt-dlp"

[download]
user_agent = "Mozilla/5.0 ..."
referer = "https://www.youtube.com/"

[album]
format = "{artist}のお歌"

# チャンネルディレクトリ名 → (アーティスト名, カテゴリ)
[channels.KAF]
artist = "花譜"
category = "神椿Studio"
```

## 対応チャンネル

| チャンネル | アーティスト | カテゴリ |
|-----------|------------|---------|
| 春猿火 ⧸ Harusaruhi | 春猿火 | 神椿Studio |
| KAF | 花譜 | 神椿Studio |
| RIM | 理芽 | 神椿Studio |
| 幸祜 - KOKO - | KOKO | 神椿Studio |
| ヰ世界情緒 -Isekaijoucho- | ヰ世界情緒 | 神椿Studio |
| HIMEHINA Channel | HIMEHINA | Vtuber |
| VALIS | VALIS | 深脊界Studio |
| 明透 -ᴀsᴜ- | 明透 | 深脊界Studio |

## タイトルパーサー

17パターンを優先度順に適用し、最初にマッチしたパターンでメタデータを抽出する。

### カバー曲パターン

| ID | パターン | 例 |
|----|---------|-----|
| C1 | `【歌ってみた】「<曲> ⧸ <原曲者>」covered by <歌手>` | 喰らいながら (Cover) |
| C2 | `【歌ってみた】<曲> ⧸ covered by <歌手>` | モエチャッカファイア (Cover) |
| C5 | `【歌ってみた】<曲> - <原曲者> covered by <歌手>` | Plazma (Cover) |
| C6 | `<曲> - <原曲者> Covered by <歌手> ⧸ <英名>` | stay tune (Cover) |
| C7 | `HIMEHINA『<曲>』Cover` | UNDEAD (Cover) |
| C4 | `【歌ってみた】<曲> Covered by <歌手>【...】` | レオ (Cover) |
| C3 | `【歌ってみた】<曲> by <歌手>` | 1ピース (Cover) |
| C8 | `<曲> (Rearranged Ver.) - <歌手> ⧸ <英名>` | 閃光だった (Rearranged Ver.) |

### オリジナル曲パターン

| ID | パターン | 例 |
|----|---------|-----|
| O3 | `【組曲N】<歌手> #<番号> 「<曲>」【オリジナルMV】` | 撃って |
| O1-R | `<歌手> #<番号>「<曲>(Rearranged ver.)」【オリジナルMV】` | BREATHE (Rearranged Ver.) |
| O1 | `<歌手> #<番号>「<曲>」【オリジナルMV】` | YONA YONA feat. Rin音 |
| O5 | `No.<番号>　<歌手> -<英名>- 「<曲>」【...】` | 在処 |
| O6 | `【ソロオリジナルMV】VALIS − <番号>「<曲>」by <歌手>【...】` | βlack Swan |
| O7 | `【オリジナルMV】VALIS − <番号>「<曲>」【合唱】` | 共振ハートビート |
| O8 | `HIMEHINA『<曲>』MV #<タグ>` | V |
| O9 | `<歌手> - <曲> ⧸ <英名> - <英曲名>` | 閃光だった |

### ライブ

| ID | パターン | 例 |
|----|---------|-----|
| L1 | `【VALIS】<曲> #<イベント> Live ver.【...】` | 純情エトワール 【喝采カーテンコール Live ver.】 |

### 前処理

パターンマッチの前に以下を処理する:

- `(from <イベント>)` を末尾から除去し、live_eventとして保存
- `with <名前>` を末尾から除去し、タイトルとアーティストに追加

## メタデータルール

| タグ | 値 |
|------|-----|
| TITLE | フル表示名 (Cover/feat./with/Live含む) |
| ARTIST | 複数値リスト (主演者 + feat./with共演者) |
| ALBUM | `{config.artist}のお歌` |
| ALBUMARTIST | config.artist (チャンネルのメインアーティスト) |
| TRACKNUMBER | 既存最大+1で自動採番 |
| R128_TRACK_GAIN | ffmpeg loudnorm → Q7.8形式 (1/256 dB) |
| METADATA_BLOCK_PICTURE | アートワーク (base64 FLAC Picture) |

### アーティスト分割ルール

- `花譜×ヰ世界情緒` → `['花譜', 'ヰ世界情緒']` (×で分割)
- `feat. 梓川` → 主演者 + `['梓川']`
- `with 春猿火` → 主演者 + `['春猿火']`
- VALIS合唱 → 7メンバー全員 (`VALIS, CHINO, MYU, NEFFY, NINA, RARA, VITTE`)

## ファイル名正規化

タグとファイル名では異なる正規化ルールを適用する。

**タグ**: NFC正規化のみ。原文字をそのまま保持。

**ファイル名**: タグ値にfoo_fileops互換の置換テーブルを適用。

```
~ → ～,  * → ＊,  ∕ → ／,  : → ：,  > → ＞,  < → ＜,  ? → ？
Ø → O,  À → A,  ô → o,  è → e,  é → e,  ë → e,  ゔ → う
```

## ライブラリ構造

```
/Volumes/musics/
├── Opus/                           # プレイヤー用（最終成果物）
│   ├── 神椿Studio/
│   │   ├── 春猿火/春猿火のお歌/
│   │   ├── 花譜/花譜のお歌/
│   │   ├── 理芽/理芽のお歌/
│   │   ├── ヰ世界情緒/ヰ世界情緒のお歌/
│   │   └── KOKO/KOKOのお歌/
│   ├── 深脊界Studio/
│   │   ├── 明透/明透のお歌/
│   │   └── VALIS/VALISのお歌/
│   └── Vtuber/
│       └── HIMEHINA/HIMEHINAのお歌/
│
└── Original/                       # オリジナルファイル保存
    └── <Category>/<Artist>/<Album>/
        ├── Original/               # webm (ダウンロード元)
        └── Opus/                   # Opus (タグ付きコピー)
```

## テスト

```bash
uv run --with pytest pytest tests/test_parser.py -v
```

全ダウンロード済みファイル名（83件）に対するパラメタライズドテストでパーサーの正確性を検証する。

## プロジェクト構成

```
├── pyproject.toml
├── config.toml.example          # 設定ファイルのサンプル
├── src/ytmusic/
│   ├── __init__.py
│   ├── __main__.py          # python -m ytmusic
│   ├── cli.py               # argparse CLI
│   ├── config.py            # TOML設定読み込み
│   ├── models.py            # データクラス・ファイル名正規化
│   ├── downloader.py        # yt-dlp ラッパー・UA自動取得
│   ├── parser.py            # タイトルパーサー (17パターン)
│   ├── audio.py             # ffmpeg/AtomicParsley ラッパー
│   ├── tagger.py            # mutagen Opusタグ・アートワーク
│   ├── organizer.py         # トラック番号採番・ファイル配置
│   └── pipeline.py          # パイプラインオーケストレーション
├── tests/
│   └── test_parser.py       # パーサーテスト (83ケース)
├── FileOps-Presets.txt       # foo_fileops プリセット (参照用)
└── FileOps-Presets-Rename.txt
```
