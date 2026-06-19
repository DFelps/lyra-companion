from __future__ import annotations

from threading import Event
import time

import numpy as np
import sounddevice as sd

from app.avatar.state import set_avatar_state, set_mode, set_mouth_level

_lipsync_stop_event = Event()


def request_lipsync_stop() -> None:
    _lipsync_stop_event.set()
    try:
        sd.stop()
    except Exception:
        pass


def clear_lipsync_stop() -> None:
    _lipsync_stop_event.clear()


def _level_from_rms(rms: float) -> int:
    if rms < 0.012:
        return 0
    if rms < 0.028:
        return 1
    if rms < 0.055:
        return 2
    return 3


def play_with_lipsync(wav: object, sample_rate: int = 24000, expression: str = "neutral") -> None:
    clear_lipsync_stop()
    audio = np.asarray(wav, dtype=np.float32)

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    if audio.size == 0:
        set_mode("idle")
        return

    set_mode("speaking", expression=expression)

    frame_seconds = 0.055
    frame_size = max(1, int(sample_rate * frame_seconds))
    started_at = time.perf_counter()

    sd.stop()
    sd.play(audio, sample_rate, blocking=False)

    try:
        while not _lipsync_stop_event.is_set():
            elapsed = time.perf_counter() - started_at
            start = int(elapsed * sample_rate)

            if start >= audio.size:
                break

            frame = audio[start:start + frame_size]
            rms = float(np.sqrt(np.mean(np.square(frame)))) if frame.size else 0.0
            set_mouth_level(_level_from_rms(rms))
            time.sleep(frame_seconds)

        if _lipsync_stop_event.is_set():
            sd.stop()
        else:
            sd.wait()
    finally:
        set_avatar_state(mode="idle", speaking=False, mouth_level=0, mouth="closed", eye="open")
        clear_lipsync_stop()
