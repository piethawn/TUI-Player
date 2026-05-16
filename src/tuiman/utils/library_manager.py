import hashlib
from pprint import pprint
from textual.widgets import Input, OptionList
from mutagen.id3 import ID3, APIC
from mutagen.mp4 import MP4
from pathlib import Path
from .caching import Cache

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def search_function(object, event: Input.Changed, iterables) -> None:
    """search helper function
        :param object: self instance of class Input
        :param event: event of class Input
        :param iterables: the song/ album list
    """
    query = event.value.lower()

    filtered = [a for a in iterables if query in a.lower()]

    option_list = object.query_one(OptionList)
    option_list.clear_options()
    for song_or_album in filtered:
        option_list.add_option(song_or_album)

async def _extract_album_art(album_path: Path, songs: dict, cache: Cache) -> str:
    """Try cache first, then extract from ID3/MP4 tags, store result in cache."""
    cached = await cache.find_album_art_cache(str(album_path))
    if cached:
        return cached

    for song_path in songs.values():
        try:
            suffix = Path(song_path).suffix.lower()
            if suffix in {".m4a", ".aac", ".mp4"}:
                tags = MP4(song_path)
                covers = tags.get("covr", [])
                if covers:
                    return await cache.create_album_art_cache(str(album_path), bytes(covers[0]))
            else:
                tags = ID3(song_path)
                for tag in tags.values():
                    if isinstance(tag, APIC):
                        return await cache.create_album_art_cache(str(album_path), tag.data)
        except Exception:
            continue

    return ""


def _load_album(album_path: Path, recursive: bool = False) -> dict | None:
    songs = {}
    scan_fn = album_path.rglob if recursive else album_path.glob

    for extension in SUPPORTED_AUDIO_EXTENSIONS:
        for entry in scan_fn(f"*{extension}"):
            songs[entry.stem] = str(entry)

    if not songs:
        return None

    # Sort by filename for consistent ordering
    songs = dict(sorted(songs.items(), key=lambda kv: kv[0].casefold()))
    return {"songs": songs, "album_art": ""}


async def load_library(root_dir: str, cache: Cache) -> dict:
    library = {}
    seen_names = {}  # name -> count of times seen
    root_path = Path(root_dir).expanduser().resolve()

    album_paths = set()
    for extension in SUPPORTED_AUDIO_EXTENSIONS:
        for match in root_path.rglob(f"*{extension}"):
            album_paths.add(match.parent)

    if not album_paths:
        album_paths = {root_path}

    # Root is handled separately as a flat album — skip it here to avoid showing
    # only its direct children as a partial entry alongside the full flat album.
    album_paths.discard(root_path)

    for album_path in sorted(album_paths, key=lambda e: e.name.casefold()):
        album = _load_album(album_path)
        if album is None:
            continue

        album["album_art"] = await _extract_album_art(album_path, album["songs"], cache)

        name = album_path.name
        if name not in seen_names:
            seen_names[name] = 0
            library[name] = album
        else:
            seen_names[name] += 1
            library[f"{name} ({seen_names[name]})"] = album

    # Always prepend root as a flat album containing every track recursively.
    # This lets users browse all songs regardless of subdirectory structure.
    root_album = _load_album(root_path, recursive=True)
    if root_album:
        root_album["album_art"] = await _extract_album_art(root_path, root_album["songs"], cache)
        root_name = root_path.name
        library = {root_name: root_album, **{k: v for k, v in library.items() if k != root_name}}

    return library


def get_song_art(song_path: str, cache: Cache) -> str:
    """Return a cached image path for this song's embedded cover art, or '' if none."""
    key = hashlib.md5(song_path.encode()).hexdigest()
    cache_file = cache.album_art_path / f"{key}.jpg"

    if cache_file.exists():
        return str(cache_file)

    try:
        suffix = Path(song_path).suffix.lower()
        if suffix in {".m4a", ".aac", ".mp4"}:
            tags = MP4(song_path)
            covers = tags.get("covr", [])
            if covers:
                cache_file.write_bytes(bytes(covers[0]))
                return str(cache_file)
        else:
            tags = ID3(song_path)
            for tag in tags.values():
                if isinstance(tag, APIC):
                    cache_file.write_bytes(tag.data)
                    return str(cache_file)
    except Exception:
        pass

    return ""


if "__main__" == __name__:
    library = load_library("../../../data")
    # print(*library.get("album2", []).keys())
    pprint(library)
    # print(list(library.values())[0]['album_art'])
    # print([*library.keys()])
    # for album in library:
    #     print(album)
    #print(next((songs["Chic 'N' Stu.mp3"] for album in library.values() for songs in [album['songs']] if "Chic 'N' Stu.mp3" in songs), ""))
