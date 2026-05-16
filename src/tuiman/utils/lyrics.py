import asyncio
import os
import re
import httpx
import mutagen.id3
from mutagen.mp4 import MP4
from httpx import ReadTimeout
from .caching import Cache

BASE_URL = "https://lrclib.net/api/search"
lyrics_cache = Cache()

async def lrclib(**kwargs)->str:
    params = {
    "track_name": kwargs.get("title", None),
    "artist_name": kwargs.get("artist", None),
    "album_name": kwargs.get("album", None)
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=15.0)) as client:
        response = await client.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        first_match = data[0].get("syncedLyrics") if data else None
        return first_match

async def parse_lrc_lyrics(lrc_text: str) -> list[tuple[float, str]]:
    pattern = re.compile(r'\[(\d+):(\d+\.\d+)\]\s*(.*)')
    results = []

    for line in lrc_text.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        minutes, seconds, text = int(m.group(1)), float(m.group(2)), m.group(3).strip()
        if text:
            ts = round(minutes * 60 + seconds, 2)
            results.append((ts, text))

    return sorted(results, key=lambda x: x[0])


def _meta_from_filename(path: str) -> dict:
    """Parse artist/title from SoundCloud-style filenames like '[ID] Artist – Title'."""
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r'^\[\d+\]\s*', '', stem)  # strip leading [ID]
    parts = re.split(r'\s+[–\-]\s+', stem, maxsplit=1)
    if len(parts) == 2:
        return {"artist": parts[0].strip(), "title": parts[1].strip()}
    return {"title": stem.strip()}


async def extract_lyrics(path: str) -> dict:
    """
    Extracts synced lyrics from embedded tags (SYLT for mp3, or unsync for m4a).
    Falls back to LRCLIB using embedded or filename-parsed metadata.
    Stores lyrics in .cache.
    Returns {"lyrics": [(timestamp_secs: float, text: str), ...]}
    """
    if not os.path.exists(path):
        return {"lyrics": []}

    suffix = os.path.splitext(path)[1].lower()
    song_meta = {}

    if suffix in {".m4a", ".aac", ".mp4"}:
        try:
            tags = MP4(path)
            if "\xa9nam" in tags:
                song_meta["title"] = tags["\xa9nam"][0]
            if "\xa9ART" in tags:
                song_meta["artist"] = tags["\xa9ART"][0]
            if "\xa9alb" in tags:
                song_meta["album"] = tags["\xa9alb"][0]
        except Exception:
            pass
    else:
        try:
            tags = mutagen.id3.ID3(path)
        except mutagen.id3.ID3NoHeaderError:
            tags = {}

        for key in tags.keys():
            if key.startswith("SYLT"):
                sylt = tags[key]
                lyrics = [
                    (round(ms / 1000.0, 3), text.strip())
                    for text, ms in sylt.text
                    if text.strip()
                ]
                lyrics.sort(key=lambda x: x[0])
                await lyrics_cache.create_cache(song_path=path, lyrics=lyrics)
                return {"lyrics": lyrics}
            if key.startswith("TIT2"):
                song_meta["title"] = tags[key].text[0] if tags[key].text else None
            if key.startswith("TPE1"):
                song_meta["artist"] = tags[key].text[0] if tags[key].text else None
            if key.startswith("TALB"):
                song_meta["album"] = tags[key].text[0] if tags[key].text else None

    # Fill missing title/artist from filename
    if not song_meta.get("title"):
        song_meta.update(_meta_from_filename(path))

    # Try to fetch synced lyrics from LRCLIB
    try:
        synced_lyrics = await lrclib(**song_meta)
    except (ReadTimeout, Exception):
        synced_lyrics = None

    if synced_lyrics:
        lyrics = await parse_lrc_lyrics(lrc_text=synced_lyrics)
        await lyrics_cache.create_cache(song_path=path, lyrics=lyrics)
        return {"lyrics": lyrics}

    await lyrics_cache.create_cache(song_path=path, lyrics=[])
    return {"lyrics": []}

if "__main__" == __name__:
    # pprint(extract_lyrics("../data/album2/Human Nature - lyrics.mp3"))
    # {'lyrics': [(10.72, 'Looking out'),
    #             (13.35, 'Across the nighttime'),
    # pprint(extract_lyrics(""))
    lyrics = asyncio.run(lrclib(
            title="",
            artist="",
            album=""
        ))
    print(lyrics)
    # print(asyncio.run(extract_lyrics(path= "../data/exeter/IMAGINARY.mp3")))
