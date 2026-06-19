from pathlib import Path
import re
import time
import uuid

import numpy as np
import sounddevice as sd
import soundfile as sf
import torch

from threading import Lock
from TTS.api import TTS


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "data" / "audio" / "generated"
REFERENCE_WAV = BASE_DIR / "data" / "voice" / "reference" / "lyra_reference.wav"

SAMPLE_RATE = 24000
MAX_TEXT_CHARS = 160
MAX_CHUNK_CHARS = 45
CHUNK_PAUSE_SECONDS = 0.04
WARMUP_TEXT = "Lyra pronta"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_tts = None
_tts_device = None
_tts_lock = Lock()
_tts_infer_lock = Lock()
_warmed_up = False

TTS_CONFIG = {
    "language": "pt",
    "temperature": 0.2,
    "repetition_penalty": 2.5,
    "top_k": 20,
    "top_p": 0.7,
    "speed": 1.0,
}


def is_available() -> bool:
    return REFERENCE_WAV.is_file()


def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_tts() -> TTS:
    global _tts, _tts_device

    with _tts_lock:
        if _tts is None:
            _tts_device = get_device()
            print(f"[TTS] carregando XTTS em {_tts_device}")

            if _tts_device == "cuda":
                print(f"[TTS] GPU: {torch.cuda.get_device_name(0)}")

            _tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            _tts.to(_tts_device)

        return _tts


def normalize_tts_text(text: str) -> str:
    text = text.strip()
    text = text.replace("\n", " ")
    text = text.replace("...", ",")
    text = text.replace("…", ",")
    text = text.replace(".", ",")
    text = text.replace("!", ",")
    text = text.replace("?", ",")
    text = text.replace(";", ",")
    text = text.replace(":", ",")
    text = text.replace("—", ",")
    text = text.replace("–", ",")
    text = text.replace('"', "")
    text = text.replace("'", "")

    text = re.sub(r",+", ",", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip(" ,")


def split_tts_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    chunks = []

    for part in parts:
        if len(part) <= max_chars:
            chunks.append(part)
            continue

        words = part.split()
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip() if current else word

            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = word

        if current:
            chunks.append(current)

    return chunks


def warmup_tts() -> None:
    global _warmed_up

    if _warmed_up:
        return

    if not is_available():
        print(f"[TTS] referência não encontrada: {REFERENCE_WAV}")
        return

    started_at = time.perf_counter()
    print("[TTS] iniciando warmup")

    tts = get_tts()

    with _tts_infer_lock:
        with torch.inference_mode():
            tts.tts(
                text=WARMUP_TEXT,
                speaker_wav=str(REFERENCE_WAV),
                **TTS_CONFIG,
            )

    _warmed_up = True
    elapsed = time.perf_counter() - started_at
    print(f"[TTS] warmup concluído em {elapsed:.2f}s")


def generate_audio(text: str) -> tuple[str, np.ndarray] | None:
    if not text or not text.strip():
        return None

    if not is_available():
        print(f"[TTS] referência não encontrada: {REFERENCE_WAV}")
        return None

    normalized_text = normalize_tts_text(text)[:MAX_TEXT_CHARS]

    if not normalized_text:
        return None

    output_path = OUTPUT_DIR / f"{uuid.uuid4()}.wav"
    device = get_device()
    started_at = time.perf_counter()
    chunks = split_tts_chunks(normalized_text)

    print(f"[TTS] texto: {normalized_text}")
    print(f"[TTS] device: {device}")
    print(f"[TTS] chars: {len(normalized_text)}")
    print(f"[TTS] chunks: {len(chunks)}")
    print(f"[TTS] referência: {REFERENCE_WAV.name} ({REFERENCE_WAV.stat().st_size / 1024:.0f} KB)")

    if device == "cuda":
        print(f"[TTS] VRAM antes: {torch.cuda.memory_allocated(0) / 1024**2:.0f} MB")

    tts = get_tts()
    generated_parts = []

    with _tts_infer_lock:
        with torch.inference_mode():
            for index, chunk in enumerate(chunks, start=1):
                print(f"[TTS] chunk {index}/{len(chunks)}: {chunk}")

                part = tts.tts(
                    text=chunk,
                    speaker_wav=str(REFERENCE_WAV),
                    **TTS_CONFIG,
                )

                part = np.asarray(part, dtype=np.float32)

                if part.size > 0:
                    generated_parts.append(part)

    if not generated_parts:
        return None

    if len(generated_parts) == 1:
        wav = generated_parts[0].astype(np.float32)
    else:
        pause = np.zeros(int(SAMPLE_RATE * CHUNK_PAUSE_SECONDS), dtype=np.float32)
        wav_parts = []

        for index, part in enumerate(generated_parts):
            wav_parts.append(part)

            if index < len(generated_parts) - 1:
                wav_parts.append(pause)

        wav = np.concatenate(wav_parts).astype(np.float32)

    sf.write(str(output_path), wav, SAMPLE_RATE)

    if device == "cuda":
        print(f"[TTS] VRAM depois: {torch.cuda.memory_allocated(0) / 1024**2:.0f} MB")

    elapsed = time.perf_counter() - started_at
    print(f"[TTS] áudio gerado em {elapsed:.2f}s: {output_path}")

    return str(output_path), wav


def play_audio(wav: object, sample_rate: int = SAMPLE_RATE) -> None:
    sd.stop()
    sd.play(np.asarray(wav, dtype=np.float32), sample_rate)
    sd.wait()


def speak(text: str) -> str | None:
    from app.avatar.lipsync import play_with_lipsync

    generated = generate_audio(text)
    if not generated:
        return None

    output_path, wav = generated
    play_with_lipsync(wav, SAMPLE_RATE)

    return output_path