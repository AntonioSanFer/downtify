---
icon: lucide/mic-2
---

# Artist Search & Watchlist

Besides single track, album and playlist links, Downtify can work from an **artist** — found by name or pasted as a Spotify artist URL. You can grab an artist's entire discography in one click, or add the artist to a watchlist that auto-downloads new releases over time.

## Search by name

1. Type an artist's name into the search bar
2. Matching artists appear in their own results section, above the track results
3. From an artist card you can:
    - **Download the full discography** (⬇)
    - **Add the artist to your watchlist** (👁)
    - **Open the artist on Spotify** (↗)

Each artist card shows the artist's photo, pulled from Spotify's anonymous web-player API alongside the name. Artists without a profile image fall back to a placeholder avatar.

## Downloading a discography

Pasting a Spotify artist URL (`https://open.spotify.com/artist/…`) into the search bar — or clicking the download button on an artist card — resolves the artist's **complete, de-duplicated** catalog and queues every track through the same pipeline as any other download.

How the catalog is assembled:

1. The artist's discography is paginated from Spotify (albums, singles and other releases)
2. Releases are ordered with full **albums first**, then singles and appearances
3. Duplicate releases (same title and track count) are collapsed
4. Tracks are de-duplicated by Spotify ID and by *(title, primary artist)* — so a song that appears on both an album and a single is only downloaded once

## Artist Watchlist

The Artist Watchlist mirrors the [Playlist Monitor](playlist-monitor.md), but for artists: Downtify periodically re-reads a watched artist's discography and automatically downloads any **newly released** tracks.

### Adding an artist

1. Open the eye icon in the navigation bar and switch to the **Artists** section
2. Paste a Spotify artist URL
3. Choose a check interval
4. Click **Watch**

When you add an artist, Downtify runs an initial backfill: every track currently in the discography is recorded as "seen" and downloaded. From then on, only releases that appear *after* you added the artist are downloaded. If a track's file is later deleted from disk, it is re-downloaded on the next check.

### Check intervals

Walking an entire discography is heavier than re-reading a single playlist, so artist checks use longer intervals than playlists and default to **once a day**.

| Label | Minutes | Best for |
|-------|---------|----------|
| Every 12 hours | 720 | Very active artists |
| Every day | 1 440 (default) | Most artists |
| Every 3 days | 4 320 | |
| Every week | 10 080 | |
| Every 2 weeks | 20 160 | |
| Every month | 43 200 | Rarely releasing artists |

You can change an existing artist's interval at any time from its monitor card without removing and re-adding it.

### Managing watched artists

From the Monitor page you can:

- **Pause / Resume** — temporarily disable an artist without removing it
- **Force check** — trigger an immediate check outside the scheduled interval
- **Remove** — stop watching an artist and delete its record (downloaded files are kept)

## Storage

Watchlist state lives in the same SQLite database as the Playlist Monitor (`/data/downtify_monitor.db`). It records:

- Each monitored artist (Spotify ID, name, URL, interval, enabled state, last check time)
- Every track successfully downloaded per artist, including the filename on disk

## A note on the Spotify API

Artist search and discography rely on Spotify's **partner GraphQL** endpoint with the anonymous web-player token — the same token Downtify already uses for playlist pagination. No Spotify account, Premium subscription or API key is required, consistent with the rest of Downtify.
