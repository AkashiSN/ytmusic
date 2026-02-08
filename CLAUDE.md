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
# コマンド: download, update-ua, scan, parse, process
```

外部ツール依存: `ffmpeg`, `yt-dlp`, `AtomicParsley`（すべて PATH に必要）

## Architecture

### パイプライン構成

```
download → discover → parse → extract(webm→opus) → artwork → R128 → tag → organize
```

`pipeline.py` がオーケストレータとして各モジュールを呼び出す。

### モジュール構成

| モジュール | 役割 |
|---|---|
| `cli.py` | argparse による CLI エントリポイント（`ytmusic.cli:main`） |
| `config.py` | TOML 設定ファイル読み込み（`tomllib`）。優先順位: `--config` > `YTMUSIC_CONFIG` env > `~/.config/ytmusic/config.toml` |
| `models.py` | `TrackMetadata`, `SourceFiles`, `ProcessingResult` の frozen dataclass。ファイル名サニタイズ（NFC 正規化 + FileOps 互換置換テーブル） |
| `parser.py` | **最重要モジュール**。17 種の正規表現パターン（C1-C8: カバー、O1-O9: オリジナル、L1: ライブ）を優先順位付きで適用し、タイトル・アーティスト・カバー判定等を抽出 |
| `downloader.py` | yt-dlp ラッパー。webm（音声）+ m4a（サムネイル付き）をダウンロード |
| `audio.py` | ffmpeg（Opus 抽出、R128 計算）と AtomicParsley（アートワーク抽出）のラッパー |
| `tagger.py` | mutagen で Opus ファイルに Vorbis Comment を書き込み（TITLE, ARTIST, ALBUM, R128_TRACK_GAIN, METADATA_BLOCK_PICTURE 等） |
| `organizer.py` | トラック番号の自動採番とライブラリディレクトリへのファイル配置 |
| `pipeline.py` | 全体のオーケストレーション。dry-run / interactive モード対応 |

### 重要な設計判断

- **R128 ゲイン**: Q7.8 形式（1/256 dB 単位）で Vorbis Comment に記録
- **パーサーのパターン順序**: 番号順に厳密な優先度を持つ。新パターン追加時は既存パターンとの干渉に注意
- **ファイル名サニタイズ**: タグ用（NFC のみ）とファイル名用（置換テーブル適用）で別ルール
- **VALIS コーラスメンバー**: 7名のハードコードリストによる特殊処理あり
- **エラー蓄積**: `ProcessingResult` でエラーを収集しつつ処理を継続

### テスト

テストは `tests/test_parser.py` に集中（83 ケースのパラメトリックテスト）。実際の YouTube 動画タイトルを使った parser の回帰テストが中心。新しいパターンを追加する際は必ず対応するテストケースを追加すること。
