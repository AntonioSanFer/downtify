"""Tests for the artist watchlist (sqlite + check_artist, no network)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Any, Callable, Optional

import pytest

from downtify import monitor
from downtify.monitor import (
    ARTIST_DEFAULT_INTERVAL_MINUTES,
    PlaylistMonitorDB,
    check_artist,
)

_AID = 'ar1stID000000000000000'


@pytest.fixture
def db(tmp_path: Path) -> PlaylistMonitorDB:
    return PlaylistMonitorDB(tmp_path / 'monitor.db')


class _FakeDownloader:
    def __init__(self, download_dir: Path) -> None:
        self.download_dir = download_dir
        self.downloaded: list[tuple[str, Optional[str]]] = []
        self.fail_ids: set[str] = set()

    def download(
        self,
        song: dict[str, Any],
        progress_cb: Optional[Callable[[float, str], None]] = None,
        subdir: Optional[str] = None,
    ) -> str:
        if song['song_id'] in self.fail_ids:
            raise RuntimeError('download failed')
        self.downloaded.append((song['song_id'], subdir))
        name = f'{song["name"]}.mp3'
        rel = f'{subdir}/{name}' if subdir else name
        target = self.download_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'')
        return rel


def _run_check(
    artist: monitor.MonitoredArtist,
    db: PlaylistMonitorDB,
    downloader: _FakeDownloader,
) -> tuple[int, list[dict[str, Any]]]:
    messages: list[dict[str, Any]] = []

    async def _broadcast(message: dict[str, Any]) -> None:
        messages.append(message)

    async def _main() -> int:
        loop = asyncio.get_running_loop()
        return await check_artist(artist, db, downloader, _broadcast, loop)

    return asyncio.run(_main()), messages


# ---------------------------------------------------------------------------
# DB CRUD
# ---------------------------------------------------------------------------


def test_add_and_get_artist(db: PlaylistMonitorDB):
    artist = db.add_artist(_AID, 'Alias Artist', 'https://x/artist')
    assert artist.id > 0
    assert artist.interval_minutes == ARTIST_DEFAULT_INTERVAL_MINUTES
    assert artist.enabled is True
    assert artist.last_checked is None
    assert db.get_artist(artist.id) == artist
    assert db.get_artist_by_spotify_id(_AID) == artist


def test_artist_spotify_id_unique(db: PlaylistMonitorDB):
    db.add_artist(_AID, 'Alias Artist', 'u')
    with pytest.raises(sqlite3.IntegrityError):
        db.add_artist(_AID, 'Alias Artist Again', 'u2')


def test_list_update_delete_artist(db: PlaylistMonitorDB):
    artist = db.add_artist(_AID, 'Alias Artist', 'u', 720)
    assert [a.id for a in db.list_artists()] == [artist.id]

    updated = db.update_artist(
        artist.id, interval_minutes=43200, enabled=False
    )
    assert updated is not None
    assert updated.interval_minutes == 43200
    assert updated.enabled is False

    # Unknown fields are ignored, known state kept.
    same = db.update_artist(artist.id, nonsense='x')
    assert same is not None
    assert same.interval_minutes == 43200

    assert db.delete_artist(artist.id) is True
    assert db.delete_artist(artist.id) is False
    assert db.list_artists() == []


def test_artist_track_filenames_roundtrip(db: PlaylistMonitorDB):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    db.mark_artist_track_downloaded(artist.id, 't1', 'Alias Artist/a.mp3')
    db.mark_artist_track_downloaded(artist.id, 't2', None)
    # Upsert replaces the filename
    db.mark_artist_track_downloaded(artist.id, 't1', 'Alias Artist/b.mp3')
    assert db.get_artist_track_filenames(artist.id) == {
        't1': 'Alias Artist/b.mp3',
        't2': None,
    }


def test_artist_tracks_cascade_on_delete(db: PlaylistMonitorDB):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    db.mark_artist_track_downloaded(artist.id, 't1', 'f.mp3')
    db.delete_artist(artist.id)
    assert db.get_artist_track_filenames(artist.id) == {}


# ---------------------------------------------------------------------------
# check_artist
# ---------------------------------------------------------------------------


def _tracks() -> list[dict[str, Any]]:
    return [
        {'song_id': 't1', 'name': 'Song One', 'artists': ['AliasNorth']},
        {'song_id': 't2', 'name': 'Song Two', 'artists': ['AliasNorth']},
    ]


def test_check_artist_downloads_new_tracks(
    db: PlaylistMonitorDB, tmp_path: Path, monkeypatch
):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    monkeypatch.setattr(
        monitor.spotify,
        'artist_all_tracks',
        lambda sid: ('Alias Artist', _tracks()),
    )
    downloader = _FakeDownloader(tmp_path)

    count, _messages = _run_check(artist, db, downloader)
    assert count == 2
    assert [d[0] for d in downloader.downloaded] == ['t1', 't2']
    # Files land in a per-artist subdir.
    assert all(d[1] == 'Alias Artist' for d in downloader.downloaded)

    refreshed = db.get_artist(artist.id)
    assert refreshed is not None
    assert refreshed.last_checked is not None
    assert refreshed.last_track_count == 2
    assert set(db.get_artist_track_filenames(artist.id)) == {'t1', 't2'}


def test_check_artist_skips_known_tracks(
    db: PlaylistMonitorDB, tmp_path: Path, monkeypatch
):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    monkeypatch.setattr(
        monitor.spotify,
        'artist_all_tracks',
        lambda sid: ('Alias Artist', _tracks()),
    )
    downloader = _FakeDownloader(tmp_path)
    count, _ = _run_check(artist, db, downloader)
    assert count == 2

    downloader.downloaded.clear()
    count, _ = _run_check(artist, db, downloader)
    assert count == 0
    assert downloader.downloaded == []


def test_check_artist_redownloads_deleted_file(
    db: PlaylistMonitorDB, tmp_path: Path, monkeypatch
):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    monkeypatch.setattr(
        monitor.spotify,
        'artist_all_tracks',
        lambda sid: ('Alias Artist', _tracks()[:1]),
    )
    downloader = _FakeDownloader(tmp_path)
    count, _ = _run_check(artist, db, downloader)
    assert count == 1

    # Remove the file on disk — next sweep must re-download it.
    stored = db.get_artist_track_filenames(artist.id)['t1']
    assert stored is not None
    (tmp_path / stored).unlink()

    downloader.downloaded.clear()
    count, _ = _run_check(artist, db, downloader)
    assert count == 1
    assert [d[0] for d in downloader.downloaded] == ['t1']


def test_check_artist_continues_after_download_failure(
    db: PlaylistMonitorDB, tmp_path: Path, monkeypatch
):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    monkeypatch.setattr(
        monitor.spotify,
        'artist_all_tracks',
        lambda sid: ('Alias Artist', _tracks()),
    )
    downloader = _FakeDownloader(tmp_path)
    downloader.fail_ids = {'t1'}

    count, _ = _run_check(artist, db, downloader)
    assert count == 1
    known = db.get_artist_track_filenames(artist.id)
    assert 't2' in known
    assert 't1' not in known


def test_check_artist_handles_fetch_failure(
    db: PlaylistMonitorDB, tmp_path: Path, monkeypatch
):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')

    def boom(sid: str):
        raise ValueError('fetch failed')

    monkeypatch.setattr(monitor.spotify, 'artist_all_tracks', boom)
    downloader = _FakeDownloader(tmp_path)
    count, _ = _run_check(artist, db, downloader)
    assert count == 0
    refreshed = db.get_artist(artist.id)
    assert refreshed is not None
    assert refreshed.last_checked is not None
    assert downloader.downloaded == []


def test_check_artist_broadcasts_progress(
    db: PlaylistMonitorDB, tmp_path: Path, monkeypatch
):
    artist = db.add_artist(_AID, 'Alias Artist', 'u')
    monkeypatch.setattr(
        monitor.spotify,
        'artist_all_tracks',
        lambda sid: ('Alias Artist', _tracks()[:1]),
    )

    class _ProgressDownloader(_FakeDownloader):
        def download(self, song, progress_cb=None, subdir=None):
            if progress_cb is not None:
                progress_cb(50.0, 'Downloading')
            return super().download(song, progress_cb, subdir)

    downloader = _ProgressDownloader(tmp_path)
    count, messages = _run_check(artist, db, downloader)
    assert count == 1
    assert any(m.get('artist_name') == 'Alias Artist' for m in messages)
