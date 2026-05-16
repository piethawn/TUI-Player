import io
import subprocess
import mutagen
import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
from pathlib import Path
from typing import Optional

PYGAME_NATIVE_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".mid", ".midi", ".opus"}

# Holds decoded audio data in memory for non-native formats so pygame doesn't
# lose the reference while the song is playing.
_audio_buffer: Optional[io.BytesIO] = None

# module-level state
_current_album: Optional[str] = None
_current_song: Optional[str] = "-----"
_current_duration: float = 0.0
_paused: bool = False

def init_player() -> None:
    """Call once at app startup."""
    pygame.mixer.init()

def _decode_with_ffmpeg(path: str) -> io.BytesIO:
    """Decode any audio file to WAV PCM in memory via ffmpeg."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", path, "-f", "wav", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", "-"],
        capture_output=True,
        timeout=60,
    )
    return io.BytesIO(result.stdout)


def play_song(data_dict: dict, song_name: str) -> bool:
    """
    Play a song by name, searching across all albums.
    Returns True on success, False if song not found.
    """
    global _current_album, _current_duration, _current_song, _paused, _audio_buffer

    for album_name, data in data_dict.items():
        if song_name not in data["songs"]:
            continue
        path = data["songs"][song_name]

        try:
            pygame.mixer.music.stop()
            if Path(path).suffix.lower() in PYGAME_NATIVE_EXTENSIONS:
                _audio_buffer = None
                pygame.mixer.music.load(path)
            else:
                _audio_buffer = _decode_with_ffmpeg(path)
                pygame.mixer.music.load(_audio_buffer)
            pygame.mixer.music.play()
            audio = mutagen.File(path)
            _current_duration = audio.info.length if audio and audio.info else 0.0
        except Exception:
            _current_duration = 0.0
            return False
        _current_album = album_name
        _current_song = song_name
        _paused = False
        return True

    return False
def pause() -> None:
    if pygame.mixer.music.get_busy() and not _paused:
        pygame.mixer.music.pause()
        globals()['_paused'] = True

def resume() -> None:
    global _paused
    if _paused:
        pygame.mixer.music.unpause()
        _paused = False

def stop() -> None:
    global _current_album, _current_song, _paused
    pygame.mixer.music.stop()
    _current_album = None
    _current_song = None
    _paused = False

def set_volume(level: float) -> None:
    """level: 0.0 to 1.0"""
    pygame.mixer.music.set_volume(max(0.0, min(1.0, level)))

def get_current() -> dict:
    return {
        "album": _current_album,
        "song": _current_song,
        "paused": _paused,
        "playing": pygame.mixer.music.get_busy()
    }

def get_progress() -> tuple[float, float, bool]:
    """Returns (elapsed_seconds, total_seconds, track_ended)."""
    if _current_song is None:
        return 0.0, 0.0, False

    track_ended = False
    raw_pos = pygame.mixer.music.get_pos()
    elapsed = max(0.0, raw_pos / 1000.0)

    if elapsed > _current_duration:
        track_ended = True

    return elapsed, _current_duration, track_ended