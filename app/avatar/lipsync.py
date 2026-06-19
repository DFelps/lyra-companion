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


def _level_from_rms(rms: float, previous: int) -> int:
    """Convert smoothed RMS into a small mouth sprite level.

    The thresholds are intentionally conservative. The renderer also throttles
    mouth swaps, so this avoids the old "machine gun mouth" effect while still
    reacting to stronger syllables.
    """
    if rms < 0.010:
        target = 0
    elif rms < 0.024:
        target = 1
    elif rms < 0.052:
        target = 2
    else:
        target = 3
        
    if target < previous and rms > 0.014:
        return max(target, previous - 1)

    return target


def play_with_lipsync(wav: object, sample_rate: int = 24000, expression: str = "neutral") -> None:
    clear_lipsync_stop()
    audio = np.asarray(wav, dtype=np.float32)

    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    if audio.size == 0:
        set_mode("idle")
        return

    analysis_audio = audio
    peak = float(np.max(np.abs(analysis_audio))) if analysis_audio.size else 0.0
    if 0 < peak < 0.08:
        analysis_audio = analysis_audio / max(peak, 1e-6) * 0.08

    set_mode("speaking", expression=expression)

    frame_seconds = 0.048
    frame_size = max(1, int(sample_rate * frame_seconds))
    started_at = time.perf_counter()
    smoothed_rms = 0.0
    previous_level = 0
    last_written_level = -1
    last_write_at = 0.0

    sd.stop()
    sd.play(audio, sample_rate, blocking=False)

    try:
        while not _lipsync_stop_event.is_set():
            elapsed = time.perf_counter() - started_at
            start = int(elapsed * sample_rate)

            if start >= audio.size:
                break

            frame = analysis_audio[start:start + frame_size]
            rms = float(np.sqrt(np.mean(np.square(frame)))) if frame.size else 0.0

            smoothed_rms = (smoothed_rms * 0.68) + (rms * 0.32)
            level = _level_from_rms(smoothed_rms, previous_level)
            previous_level = level

            now = time.perf_counter()
            if level != last_written_level and now - last_write_at >= 0.070:
                set_mouth_level(level)
                last_written_level = level
                last_write_at = now

            time.sleep(frame_seconds)

        if _lipsync_stop_event.is_set():
            sd.stop()
        else:
            sd.wait()
    finally:
        set_avatar_state(mode="idle", speaking=False, mouth_level=0, mouth="closed", eye="open")
        clear_lipsync_stop()
