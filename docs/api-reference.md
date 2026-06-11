---
icon: material/api
---

# API Reference

Downtify exposes a JSON REST API used by the web UI. All endpoints are served on the same port as the web UI (default: **8000**).

## General

### `GET /api/version`

Returns the current Downtify version as a plain string.

**Response:** `"2.6.0"`

---

## Search & resolve

### `GET /api/songs/search`

Search YouTube Music by free text.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query |

**Response:** Array of song objects (up to 20 results).

---

### `GET /api/song/url`

Resolve a Spotify URL to metadata.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | yes | Spotify track, album or playlist URL |

**Response:**

- **Track URL** → single song object
- **Album URL** → array of song objects
- **Playlist URL** → array of song objects

`GET /api/url` is an alias for this endpoint.

An **artist** URL is also accepted: it resolves to the artist's full,
de-duplicated discography as an array of song objects.

---

### `GET /api/artist/search`

Search Spotify artists by name.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Artist name |

**Response:** Array of artist objects (up to 10 results):

```json
[
  {
    "artist_id": "4tZwfgrHOc3mvqYlEYSvVi",
    "name": "Daft Punk",
    "url": "https://open.spotify.com/artist/4tZwfgrHOc3mvqYlEYSvVi",
    "cover_url": "https://i.scdn.co/image/ab6761610000e5eb…",
    "followers": 0,
    "genres": [],
    "source": "spotify"
  }
]
```

`cover_url` is the artist's avatar image (largest available size).
`followers` and `genres` are not exposed by the search endpoint and are
returned as `0` / `[]`.

---

### `GET /api/artist/tracks`

Resolve the full, de-duplicated discography for an artist.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | yes | Spotify artist URL or bare artist id |

**Response:**

```json
{
  "artist_id": "4tZwfgrHOc3mvqYlEYSvVi",
  "name": "Daft Punk",
  "url": "https://open.spotify.com/artist/4tZwfgrHOc3mvqYlEYSvVi",
  "tracks": [ /* array of song objects */ ]
}
```

---

## Downloads

### `POST /api/download/url`

Download a single track. Blocks until complete.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | yes | Spotify track URL or YouTube URL |
| `client_id` | string | no | WebSocket client ID for progress events |

**Response:** Filename string of the downloaded file.

---

### `POST /api/download/batch`

Download multiple tracks concurrently (up to 4 at a time). Returns immediately; progress is broadcast over WebSocket.

**Request body:**

```json
{
  "songs": [ /* array of song objects */ ],
  "playlist_url": "https://open.spotify.com/playlist/…",
  "generate_m3u": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `songs` | array | Song objects to download |
| `playlist_url` | string | Optional. Used to determine the playlist subfolder and M3U name. |
| `generate_m3u` | boolean | Whether to write an M3U after the batch finishes. Default: `true`. |

**Response:**

```json
{
  "job_ids": ["track_id_1", "track_id_2"],
  "count": 2
}
```

---

## Queue

### `GET /api/queue`

List all download jobs (queued, in progress, done, error).

**Response:** Array of job objects.

---

### `DELETE /api/queue`

Clear the entire download queue/history.

**Response:** `{ "cleared": true }`

---

### `DELETE /api/queue/item`

Remove a single job from the queue.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `song_id` | string | yes | Job ID |

**Response:** `{ "removed": true }` or `{ "removed": false }`

---

## Settings

### `GET /api/settings`

Return the current settings.

**Response:**

```json
{
  "audio_providers": ["youtube-music"],
  "lyrics_providers": ["lrclib"],
  "download_lyrics": true,
  "format": "mp3",
  "bitrate": "320",
  "output": "{artists} - {title}.{output-ext}",
  "generate_m3u": true,
  "organize_by_artist": false
}
```

---

### `POST /api/settings/update`

Update one or more settings. Takes effect immediately and is persisted to disk.

**Request body:** Partial settings object with any subset of the fields above.

**Response:** Full settings object after the update.

---

## File management

### `GET /list`

List all audio files in the downloads directory (recursive).

**Response:** Sorted array of relative paths (e.g. `["My Playlist/Song.mp3", "Artist - Track.mp3"]`).

---

### `DELETE /delete`

Delete a downloaded file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | string | yes | Relative path to the file (as returned by `/list`) |

**Response:** `{ "deleted": true }` or `{ "deleted": false, "error": "…" }`

---

### `GET /cover`

Return the embedded cover art for a file.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | string | yes | Relative path to the file |

**Response:** Image bytes (`image/jpeg` or `image/png`). Returns `404` if no embedded cover is found.

---

## Playlist M3U

### `POST /api/playlist/m3u`

Write an M3U file for a playlist after per-track downloads are complete.

**Request body:**

```json
{
  "playlist_url": "https://open.spotify.com/playlist/…",
  "tracks": [
    {
      "filename": "My Playlist/Artist - Title.mp3",
      "title": "Title",
      "artist": "Artist",
      "duration": 210
    }
  ]
}
```

**Response:** `{ "path": "/downloads/…/playlist.m3u", "count": 12 }`

---

## Playlist Monitor

### `GET /api/monitor/playlists`

List all monitored playlists.

**Response:** Array of playlist monitor objects.

---

### `POST /api/monitor/playlists`

Add a playlist to the monitor. Triggers an immediate initial download.

**Request body:**

```json
{
  "url": "https://open.spotify.com/playlist/…",
  "interval_minutes": 60
}
```

**Response:** Playlist monitor object.

---

### `PATCH /api/monitor/playlists/{playlist_id}`

Update a monitored playlist (interval, enabled state).

**Request body:** Partial object with `interval_minutes` and/or `enabled`.

**Response:** Updated playlist monitor object.

---

### `DELETE /api/monitor/playlists/{playlist_id}`

Stop monitoring a playlist.

**Response:** `{ "deleted": true }` or `{ "deleted": false }`

---

### `POST /api/monitor/playlists/{playlist_id}/check`

Trigger an immediate check for a specific playlist outside the normal schedule.

**Response:** `{ "downloaded": 3 }`

---

## Artist Monitor

### `GET /api/monitor/artists`

List all monitored artists.

**Response:** Array of artist monitor objects.

---

### `POST /api/monitor/artists`

Add an artist to the watchlist. Triggers an immediate initial backfill.

**Request body:**

```json
{
  "url": "https://open.spotify.com/artist/…",
  "interval_minutes": 1440
}
```

`interval_minutes` defaults to **1440** (once a day) when omitted.

**Response:** Artist monitor object. Returns `409` if the artist is already
being monitored.

---

### `PATCH /api/monitor/artists/{artist_id}`

Update a monitored artist (interval, enabled state).

**Request body:** Partial object with `interval_minutes` and/or `enabled`.

**Response:** Updated artist monitor object. `404` if not found.

---

### `DELETE /api/monitor/artists/{artist_id}`

Stop watching an artist (downloaded files are kept).

**Response:** `{ "deleted": true, "id": 1 }`. `404` if not found.

---

### `POST /api/monitor/artists/{artist_id}/check`

Trigger an immediate check for a specific artist outside the normal
schedule. Runs in the background.

**Response:** `{ "status": "check_started", "id": 1 }`

---

## WebSocket

### `WS /api/ws`

Real-time download progress events.

| Query parameter | Required | Description |
|----------------|----------|-------------|
| `client_id` | yes | Unique client identifier (UUID recommended) |

**Events received from the server:**

```json
{
  "song": { /* song metadata object */ },
  "progress": 42.5,
  "message": "Downloading…",
  "status": "downloading",
  "filename": null
}
```

`status` is one of: `queued` · `downloading` · `done` · `error`.

`filename` is set (non-null) on the final `done` event.
