"""Tests for playlist generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from ytmusic.playlist import _collect_tracks, write_playlist


def _make_audio_files(directory: Path, names: list[str]) -> None:
    """Create empty audio files in directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).touch()


def _make_exclude(directory: Path, entries: list[str]) -> None:
    """Create .exclude file."""
    (directory / ".exclude").write_text("\n".join(entries) + "\n")


class TestCollectTracks:
    def test_basic_collection_and_sort(self, tmp_path: Path) -> None:
        """Collect audio files sorted by track number."""
        album = tmp_path / "Artist" / "Album"
        playlists = tmp_path / "Playlists"
        playlists.mkdir()
        _make_audio_files(album, [
            "3. Track C.opus",
            "1. Track A.opus",
            "2. Track B.opus",
        ])
        _make_exclude(album, [])  # empty .exclude to stop recursion

        tracks = _collect_tracks(album, playlists)

        assert len(tracks) == 3
        assert "Track A" in tracks[0]
        assert "Track B" in tracks[1]
        assert "Track C" in tracks[2]

    def test_exclude_file(self, tmp_path: Path) -> None:
        """Respect .exclude file entries."""
        album = tmp_path / "Artist" / "Album"
        playlists = tmp_path / "Playlists"
        playlists.mkdir()
        _make_audio_files(album, [
            "1. Track A.opus",
            "2. MC Talk.opus",
            "3. Track B.opus",
        ])
        _make_exclude(album, ["2. MC Talk.opus"])

        tracks = _collect_tracks(album, playlists)

        assert len(tracks) == 2
        filenames = [Path(t).name for t in tracks]
        assert "2. MC Talk.opus" not in filenames
        assert "1. Track A.opus" in filenames
        assert "3. Track B.opus" in filenames

    def test_recursive_collection(self, tmp_path: Path) -> None:
        """Recurse into subdirectories when no .exclude at parent."""
        artist = tmp_path / "Artist"
        playlists = tmp_path / "Playlists"
        playlists.mkdir()

        album1 = artist / "Album1"
        album2 = artist / "Album2"
        _make_audio_files(album1, ["1. Song A.opus", "2. Song B.opus"])
        _make_audio_files(album2, ["1. Song C.opus"])
        _make_exclude(album1, [])
        _make_exclude(album2, [])

        tracks = _collect_tracks(artist, playlists)

        assert len(tracks) == 3

    def test_m4a_extension(self, tmp_path: Path) -> None:
        """.m4a files are also collected."""
        album = tmp_path / "Artist" / "Album"
        playlists = tmp_path / "Playlists"
        playlists.mkdir()
        _make_audio_files(album, [
            "1. Track A.m4a",
            "2. Track B.opus",
        ])
        _make_exclude(album, [])

        tracks = _collect_tracks(album, playlists)

        assert len(tracks) == 2

    def test_non_audio_files_ignored(self, tmp_path: Path) -> None:
        """Non-audio files are not collected."""
        album = tmp_path / "Artist" / "Album"
        playlists = tmp_path / "Playlists"
        playlists.mkdir()
        _make_audio_files(album, [
            "1. Track A.opus",
            "cover.jpg",
            "notes.txt",
        ])
        _make_exclude(album, [])

        tracks = _collect_tracks(album, playlists)

        assert len(tracks) == 1
        assert "Track A" in tracks[0]

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        album = tmp_path / "Artist" / "Album"
        album.mkdir(parents=True)
        playlists = tmp_path / "Playlists"
        playlists.mkdir()

        tracks = _collect_tracks(album, playlists)

        assert tracks == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        """Non-existent directory returns empty list."""
        playlists = tmp_path / "Playlists"
        playlists.mkdir()

        tracks = _collect_tracks(tmp_path / "nonexistent", playlists)

        assert tracks == []

    def test_relative_paths(self, tmp_path: Path) -> None:
        """Returned paths are relative to playlists_base."""
        album = tmp_path / "Category" / "Artist" / "Album"
        playlists = tmp_path / "Playlists"
        playlists.mkdir()
        _make_audio_files(album, ["1. Track.opus"])
        _make_exclude(album, [])

        tracks = _collect_tracks(album, playlists)

        assert len(tracks) == 1
        # Path should be relative and go up from Playlists
        assert tracks[0].startswith("..")


class TestWritePlaylist:
    def test_basic_output(self, tmp_path: Path) -> None:
        """Write m3u8 with header and track lines."""
        output = tmp_path / "m3u8" / "test.m3u8"
        tracks = [
            "../Category/Artist/Album/1. Track A.opus",
            "../Category/Artist/Album/2. Track B.opus",
        ]

        write_playlist(tracks, output)

        content = output.read_text(encoding="utf-8")
        lines = content.splitlines()
        assert lines[0] == "#"
        assert lines[1] == "../Category/Artist/Album/1. Track A.opus"
        assert lines[2] == "../Category/Artist/Album/2. Track B.opus"
        assert len(lines) == 3

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created automatically."""
        output = tmp_path / "deep" / "nested" / "dir" / "test.m3u8"

        write_playlist(["track.opus"], output)

        assert output.exists()

    def test_empty_playlist(self, tmp_path: Path) -> None:
        """Empty track list produces header-only file."""
        output = tmp_path / "empty.m3u8"

        write_playlist([], output)

        content = output.read_text(encoding="utf-8")
        assert content == "#\n"
