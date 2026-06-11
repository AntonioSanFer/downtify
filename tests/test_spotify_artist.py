"""Tests for Spotify artist resolution helpers (no network)."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import pytest

from downtify import spotify
from downtify.spotify import (
    artist_albums_from_id,
    artist_all_tracks,
    artist_info_from_id,
    parse_spotify_url,
    search_artists,
)

_ARTIST_ID = 'ar1stID000000000000000'
_AL1 = 'AliasNorth'
_AL2 = 'AliasSouth'


class _FakeResponse:
    def __init__(
        self,
        *,
        text: str = '',
        payload: Optional[Any] = None,
        status: int = 200,
    ) -> None:
        self.text = text
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self) -> Any:
        return self._payload


def _embed_html(entity: dict[str, Any], token: str = 'test-token') -> str:
    payload = {
        'props': {
            'pageProps': {
                'state': {
                    'data': {'entity': entity},
                    'settings': {
                        'session': {
                            'accessToken': token,
                            'accessTokenExpirationTimestampMs': (
                                (time.time() + 3600) * 1000
                            ),
                        }
                    },
                }
            }
        }
    }
    blob = json.dumps(payload)
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        f'{blob}</script></body></html>'
    )


def _artist_entity(name: str = 'Alias Artist') -> dict[str, Any]:
    return {
        'name': name,
        'type': 'artist',
        'coverArt': {
            'sources': [
                {'url': 'https://img.test/small', 'width': 64},
                {'url': 'https://img.test/big', 'width': 640},
            ]
        },
    }


def _album_entity(
    album_name: str,
    tracks: list[tuple[str, str, str]],
) -> dict[str, Any]:
    """``tracks`` is ``[(track_id, title, subtitle_artists)]``."""

    return {
        'name': album_name,
        'type': 'album',
        'releaseDate': {'isoString': '2024-06-15T00:00:00.000Z'},
        'coverArt': {
            'sources': [{'url': 'https://img.test/album', 'width': 640}]
        },
        'trackList': [
            {
                'id': tid,
                'uri': f'spotify:track:{tid}',
                'title': title,
                'subtitle': subtitle,
                'duration': 200_000,
            }
            for tid, title, subtitle in tracks
        ],
    }


def _search_suggestions_payload(
    artists: list[tuple[str, str]],
) -> dict[str, Any]:
    """``artists`` is ``[(artist_id, name)]`` → searchSuggestions shape."""

    items: list[dict[str, Any]] = [
        {
            'item': {
                '__typename': 'SearchAutoCompleteEntity',
                'data': {'text': 'noise', 'uri': 'spotify:search:noise'},
            }
        }
    ]
    for artist_id, name in artists:
        items.append({
            'item': {
                '__typename': 'ArtistResponseWrapper',
                'data': {
                    'profile': {'name': name},
                    'uri': f'spotify:artist:{artist_id}',
                    'visualIdentity': {'squareCoverImage': {}},
                    'visuals': {
                        'avatarImage': {
                            'sources': [
                                {
                                    'url': f'https://img.test/{artist_id}-160',
                                    'width': 160,
                                    'height': 160,
                                },
                                {
                                    'url': f'https://img.test/{artist_id}-640',
                                    'width': 640,
                                    'height': 640,
                                },
                            ]
                        }
                    },
                },
            }
        })
    return {
        'data': {
            'searchV2': {
                '__typename': 'SearchResultV2',
                'topResultsV2': {'itemsV2': items},
            }
        }
    }


def _discography_release(
    album_id: str,
    name: str,
    album_type: str = 'ALBUM',
    total_tracks: int = 2,
) -> dict[str, Any]:
    return {
        'releases': {
            'items': [
                {
                    'id': album_id,
                    'uri': f'spotify:album:{album_id}',
                    'name': name,
                    'type': album_type,
                    'date': {'isoString': '2024-06-15T00:00:00Z'},
                    'tracks': {'totalCount': total_tracks},
                    'coverArt': {
                        'sources': [
                            {
                                'url': f'https://img.test/{album_id}',
                                'width': 640,
                            }
                        ]
                    },
                }
            ]
        }
    }


def _discography_payload(
    releases: list[dict[str, Any]], total: int
) -> dict[str, Any]:
    return {
        'data': {
            'artistUnion': {
                'discography': {
                    'all': {'items': releases, 'totalCount': total}
                }
            }
        }
    }


@pytest.fixture(autouse=True)
def _reset_token_cache():
    spotify._token_cache['token'] = None
    spotify._token_cache['expires_at'] = 0.0
    yield
    spotify._token_cache['token'] = None
    spotify._token_cache['expires_at'] = 0.0


class _Dispatcher:
    """Routes ``requests.get`` by URL prefix, or partner GraphQL by op.

    Partner-API routes are keyed by ``op:<operationName>`` so a single
    endpoint can serve different canned responses (and paginate) per call.
    """

    def __init__(self) -> None:
        self.routes: list[tuple[str, Any]] = []
        self.calls: list[str] = []

    def add(self, prefix: str, response: _FakeResponse) -> None:
        self.routes.append((prefix, response))

    def add_op(self, operation: str, responses: list[_FakeResponse]) -> None:
        """Queue per-call responses for a partner GraphQL operation."""
        self.routes.append((f'op:{operation}', list(responses)))

    def __call__(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(url)
        if url.startswith(spotify._PARTNER_API):
            op = (kwargs.get('params') or {}).get('operationName')
            for key, value in self.routes:
                if key == f'op:{op}':
                    if isinstance(value, list):
                        return value.pop(0) if len(value) > 1 else value[0]
                    return value
            raise AssertionError(f'Unexpected partner op: {op}')
        for key, response in self.routes:
            if not key.startswith('op:') and url.startswith(key):
                return response
        raise AssertionError(f'Unexpected URL fetched: {url}')


@pytest.fixture
def dispatcher(monkeypatch) -> _Dispatcher:
    d = _Dispatcher()
    monkeypatch.setattr(spotify.requests, 'get', d)
    return d


def test_parse_spotify_url_artist():
    parsed = parse_spotify_url(
        f'https://open.spotify.com/artist/{_ARTIST_ID}?si=x'
    )
    assert parsed == ('artist', _ARTIST_ID)


def test_parse_spotify_url_artist_intl_prefix():
    parsed = parse_spotify_url(
        f'https://open.spotify.com/intl-es/artist/{_ARTIST_ID}'
    )
    assert parsed == ('artist', _ARTIST_ID)


def test_artist_info_from_id(dispatcher):
    dispatcher.add(
        f'https://open.spotify.com/embed/artist/{_ARTIST_ID}',
        _FakeResponse(text=_embed_html(_artist_entity())),
    )
    info = artist_info_from_id(_ARTIST_ID)
    assert info['artist_id'] == _ARTIST_ID
    assert info['name'] == 'Alias Artist'
    assert info['cover_url'] == 'https://img.test/big'
    assert info['url'].endswith(f'/artist/{_ARTIST_ID}')


def test_artist_info_caches_anonymous_token(dispatcher):
    dispatcher.add(
        f'https://open.spotify.com/embed/artist/{_ARTIST_ID}',
        _FakeResponse(text=_embed_html(_artist_entity(), token='tok-abc')),
    )
    artist_info_from_id(_ARTIST_ID)
    assert spotify._anonymous_token() == 'tok-abc'
    # The cached token must be reused — no extra embed fetches.
    embed_calls = [c for c in dispatcher.calls if '/embed/' in c]
    assert len(embed_calls) == 1


def test_search_artists_maps_partner_items(dispatcher):
    # Token comes from the first seed embed page.
    dispatcher.add(
        'https://open.spotify.com/embed/',
        _FakeResponse(text=_embed_html(_artist_entity())),
    )
    dispatcher.add_op(
        'searchSuggestions',
        [
            _FakeResponse(
                payload=_search_suggestions_payload([
                    (_ARTIST_ID, _AL1),
                    ('ar2ndID00000000000000', _AL2),
                ])
            )
        ],
    )
    rows = search_artists('alias', limit=5)
    assert [r['artist_id'] for r in rows] == [
        _ARTIST_ID,
        'ar2ndID00000000000000',
    ]
    row = rows[0]
    assert row['name'] == _AL1
    assert row['url'].endswith(f'/artist/{_ARTIST_ID}')
    assert row['source'] == 'spotify'
    # Avatar is read from visuals.avatarImage, largest source first.
    assert row['cover_url'] == f'https://img.test/{_ARTIST_ID}-640'


def test_search_artists_empty_query_returns_empty(dispatcher):
    assert search_artists('   ') == []
    assert dispatcher.calls == []


def test_artist_albums_paginates_and_dedupes(dispatcher):
    dispatcher.add(
        f'https://open.spotify.com/embed/artist/{_ARTIST_ID}',
        _FakeResponse(text=_embed_html(_artist_entity())),
    )
    dispatcher.add_op(
        'queryArtistDiscographyAll',
        [
            _FakeResponse(
                payload=_discography_payload(
                    [
                        _discography_release('alb1', 'First LP'),
                        # market duplicate (same title + track count)
                        _discography_release('alb1dup', 'First LP'),
                    ],
                    total=3,
                )
            ),
            _FakeResponse(
                payload=_discography_payload(
                    [
                        _discography_release(
                            'sgl1', 'Lone Single', album_type='SINGLE'
                        )
                    ],
                    total=3,
                )
            ),
        ],
    )
    albums = artist_albums_from_id(_ARTIST_ID)
    assert [a['album_id'] for a in albums] == ['alb1', 'sgl1']
    assert albums[0]['album_group'] == 'album'
    assert albums[0]['release_date'] == '2024-06-15'
    assert albums[0]['cover_url'] == 'https://img.test/alb1'
    assert albums[1]['album_group'] == 'single'


def test_artist_all_tracks_orders_albums_first_and_dedupes(monkeypatch):
    monkeypatch.setattr(
        spotify,
        'artist_info_from_id',
        lambda aid: {'artist_id': aid, 'name': 'Alias Artist'},
    )
    monkeypatch.setattr(
        spotify,
        'artist_albums_from_id',
        lambda aid: [
            {
                'album_id': 'sgl1',
                'name': 'Lead Single',
                'album_group': 'single',
            },
            {'album_id': 'alb1', 'name': 'First LP', 'album_group': 'album'},
        ],
    )
    album_tracks = {
        'alb1': [
            {'song_id': 't1', 'name': 'Song One', 'artists': [_AL1]},
            {'song_id': 't2', 'name': 'Song Two', 'artists': [_AL1]},
        ],
        # Same song released earlier as a single under a different id.
        'sgl1': [
            {'song_id': 't1single', 'name': 'Song One', 'artists': [_AL1]},
        ],
    }
    monkeypatch.setattr(
        spotify, 'album_tracks_from_id', lambda aid: album_tracks[aid]
    )

    name, tracks = artist_all_tracks(_ARTIST_ID)
    assert name == 'Alias Artist'
    # The album version wins; the single duplicate is dropped.
    assert [t['song_id'] for t in tracks] == ['t1', 't2']


def test_artist_all_tracks_skips_failing_album(monkeypatch):
    monkeypatch.setattr(
        spotify,
        'artist_info_from_id',
        lambda aid: {'artist_id': aid, 'name': 'Alias Artist'},
    )
    monkeypatch.setattr(
        spotify,
        'artist_albums_from_id',
        lambda aid: [
            {'album_id': 'bad', 'name': 'Broken', 'album_group': 'album'},
            {'album_id': 'ok', 'name': 'Good', 'album_group': 'album'},
        ],
    )

    def fake_album_tracks(aid: str):
        if aid == 'bad':
            raise ValueError('boom')
        return [{'song_id': 'tX', 'name': 'Song X', 'artists': [_AL2]}]

    monkeypatch.setattr(spotify, 'album_tracks_from_id', fake_album_tracks)
    _, tracks = artist_all_tracks(_ARTIST_ID)
    assert [t['song_id'] for t in tracks] == ['tX']


def test_resolve_artist_url_returns_tracks(monkeypatch):
    monkeypatch.setattr(
        spotify,
        'artist_all_tracks',
        lambda aid: ('Alias Artist', [{'song_id': 't1'}]),
    )
    out = spotify.resolve(f'https://open.spotify.com/artist/{_ARTIST_ID}')
    assert out == [{'song_id': 't1'}]


def test_artist_all_tracks_end_to_end_with_embeds(dispatcher):
    """Full flow over fake HTTP: embed artist + partner GraphQL + albums."""

    dispatcher.add(
        f'https://open.spotify.com/embed/artist/{_ARTIST_ID}',
        _FakeResponse(text=_embed_html(_artist_entity())),
    )
    dispatcher.add_op(
        'queryArtistDiscographyAll',
        [
            _FakeResponse(
                payload=_discography_payload(
                    [_discography_release('alb1', 'First LP')], total=1
                )
            )
        ],
    )
    dispatcher.add(
        'https://open.spotify.com/embed/album/alb1',
        _FakeResponse(
            text=_embed_html(
                _album_entity(
                    'First LP',
                    [
                        ('t1', 'Song One', f'{_AL1}, {_AL2}'),
                        ('t2', 'Song Two', _AL1),
                    ],
                )
            )
        ),
    )

    name, tracks = artist_all_tracks(_ARTIST_ID)
    assert name == 'Alias Artist'
    assert [t['song_id'] for t in tracks] == ['t1', 't2']
    assert tracks[0]['artists'] == [_AL1, _AL2]
    assert tracks[0]['album_name'] == 'First LP'
    assert tracks[0]['release_date'] == '2024-06-15'
    assert tracks[0]['cover_url'] == 'https://img.test/album'
