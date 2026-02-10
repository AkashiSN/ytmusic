# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ytmusic は YouTube からダウンロードした音楽ファイルの後処理を自動化する Python CLI ツール。主に日本の VTuber チャンネルのカバー曲・オリジナル楽曲を対象とし、yt-dlp でダウンロードした webm/m4a ファイルから Opus 抽出、アートワーク埋め込み、R128 ゲイン計算、メタデータタグ付け、ライブラリへの整理配置までを一貫して行う。

## Commands

```bash
# 依存関係のインストール（開発モード）
uv sync --dev

# テスト実行
uv run pytest

# 単一テスト実行
uv run pytest tests/test_parser.py -v -k "test_name"

# CLI 実行
uv run ytmusic <command>
# コマンド: download, scan, parse, process, playlist, sync
```

外部ツール依存: `ffmpeg`, `yt-dlp`, `AtomicParsley`（すべて PATH に必要）、`adb`（sync 機能に必要、オプション）

## Architecture

### パイプライン構成

```
download → discover → parse → extract(webm→opus) → artwork → R128 → tag → organize → playlist → sync
```

`pipeline.py` がオーケストレータとして各モジュールを呼び出す。

### モジュール構成

| モジュール | 役割 |
|---|---|
| `cli.py` | argparse による CLI エントリポイント（`ytmusic.cli:main`） |
| `config.py` | TOML 設定ファイル読み込み（`tomllib`）。優先順位: `--config` > `YTMUSIC_CONFIG` env > `~/.config/ytmusic/config.toml` |
| `models.py` | `TrackMetadata`, `SourceFiles`, `ProcessingResult` の frozen dataclass。ファイル名サニタイズ（NFC 正規化 + FileOps 互換置換テーブル） |
| `parser.py` | **最重要モジュール**。17 種の正規表現パターン（C1-C8: カバー、O1-O9: オリジナル、L1: ライブ）を優先順位付きで適用し、タイトル・アーティスト・カバー判定等を抽出。前処理で `(from <event>)` → ライブ検出、`with <name>` → suffix 前挿入も行う |
| `downloader.py` | yt-dlp ラッパー。webm（音声）+ m4a（サムネイル付き）をダウンロード。UA は設定ファイルで直接管理 |
| `audio.py` | ffmpeg（Opus 抽出、R128 計算）と AtomicParsley（アートワーク抽出）のラッパー |
| `tagger.py` | mutagen で Opus ファイルに Vorbis Comment を書き込み（TITLE, ARTIST, ALBUM, R128_TRACK_GAIN, METADATA_BLOCK_PICTURE 等） |
| `organizer.py` | トラック番号の自動採番とライブラリディレクトリへのファイル配置。ソースファイルの保持/移動/削除を `source_handling` パラメータで制御 |
| `playlist.py` | m3u8 プレイリスト生成。`.exclude` 対応の再帰走査、アーティスト/カテゴリ単位の生成 |
| `pipeline.py` | 全体のオーケストレーション。dry-run / interactive モード対応。処理後のプレイリスト自動再生成 |
| `sync.py` | ADB 経由で Android SD カードへメディアファイルを転送。デバイス/SD カード自動検出、差分同期（相対パスベース）、対話的選択に対応 |

### 重要な設計判断

- **R128 ゲイン**: Q7.8 形式（1/256 dB 単位）で Vorbis Comment に記録
- **パーサーのパターン順序**: 番号順に厳密な優先度を持つ。新パターン追加時は既存パターンとの干渉に注意
- **ファイル名サニタイズ**: タグ用（NFC のみ）とファイル名用（置換テーブル適用）で別ルール
- **VALIS コーラスメンバー**: 7名のハードコードリストによる特殊処理あり
- **エラー蓄積**: `ProcessingResult` でエラーを収集しつつ処理を継続
- **ソースファイル保持**: デフォルトではダウンロードした webm/m4a をそのまま残す。`--move-sources` でソース削除（Original/ にバックアップ）、`--clean-sources` でソース削除（バックアップなし）
- **プレイリスト**: `process` 後にデフォルトで影響プレイリストを自動再生成（`--no-playlist` で無効化）。`[playlists]` 未設定時は既存機能に影響なし
- **ADB 同期**: `process` 後にデフォルトで ADB 経由の自動同期を実行（`--no-sync` で無効化）。ADB 未接続時は警告のみでスキップ。`sync` コマンドでライブラリ全体の差分同期も可能。対象は `MEDIA_EXTENSIONS`（`.opus`, `.flac`, `.mp3`, `.m4a`, `.ogg`, `.wav`, `.aac`, `.wma`, `.m3u8`）に一致するファイル

### テスト

- `tests/test_parser.py`: 83 ケースのパラメトリックテスト。実際の YouTube 動画タイトルを使った parser の回帰テストが中心。新しいパターンを追加する際は必ず対応するテストケースを追加すること。
- `tests/test_playlist.py`: プレイリスト生成のユニットテスト（ファイル収集、`.exclude`、再帰走査、m3u8 出力形式等）。
