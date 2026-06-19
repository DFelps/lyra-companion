from pathlib import Path
from threading import Lock
from app.voice.tts_text_normalizer import make_tts_friendly

import os
import re
import time
import uuid

import numpy as np
import sounddevice as sd
import soundfile as sf
import torch


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "data" / "audio" / "generated"
REFERENCE_WAV = BASE_DIR / "data" / "voice" / "reference" / "lyra_reference.wav"
REFERENCE_TEXT = BASE_DIR / "data" / "voice" / "reference" / "lyra_reference.txt"

SAMPLE_RATE = 24000
MAX_TEXT_CHARS = 1000
WARMUP_TEXT = "Lyra pronta"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_f5 = None
_f5_lock = Lock()
_f5_infer_lock = Lock()
_warmed_up = False

F5_PTBR_DIR = BASE_DIR / "data" / "models" / "f5_ptbr"
F5_PTBR_CKPT = F5_PTBR_DIR / "model_last.safetensors"
F5_PTBR_VOCAB = F5_PTBR_DIR / "vocab.txt"

F5_CONFIG = {
    "model": os.getenv("LYRA_F5_MODEL", "F5TTS_v1_Base"),
    "ckpt_file": os.getenv("LYRA_F5_CKPT", str(F5_PTBR_CKPT)),
    "vocab_file": os.getenv("LYRA_F5_VOCAB", str(F5_PTBR_VOCAB)),
    "speed": float(os.getenv("LYRA_F5_SPEED", "0.72")),
    "nfe_step": int(os.getenv("LYRA_F5_NFE_STEP", "32")),
    "cfg_strength": float(os.getenv("LYRA_F5_CFG_STRENGTH", "1.2")),
    "sway_sampling_coef": float(os.getenv("LYRA_F5_SWAY", "-1")),
}


def is_available() -> bool:
    return REFERENCE_WAV.is_file()


def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_reference_text() -> str:
    if REFERENCE_TEXT.is_file():
        return REFERENCE_TEXT.read_text(encoding="utf-8").strip()
    return ""


def get_f5():
    global _f5

    with _f5_lock:
        if _f5 is None:
            from f5_tts.api import F5TTS

            device = get_device()
            print(f"[F5-TTS] carregando {F5_CONFIG['model']} em {device}")

            # if device == "cuda":
            #     print(f"[F5-TTS] GPU: {torch.cuda.get_device_name(0)}")

            _f5 = F5TTS(
                model=F5_CONFIG["model"],
                ckpt_file=F5_CONFIG["ckpt_file"],
                vocab_file=F5_CONFIG["vocab_file"],
                device=device,
            )
            # print(f"[F5-TTS] checkpoint: {F5_CONFIG['ckpt_file']}")
            # print(f"[F5-TTS] vocab: {F5_CONFIG['vocab_file']}")

        return _f5


def normalize_tts_text(text: str) -> str:
    text = text.strip()
    text = make_tts_friendly(text)
    text = text.replace("\n", " ")
    text = text.replace("…", ".")
    text = text.replace("...", ".")
    text = text.replace("—", ", ")
    text = text.replace("–", ", ")
    text = text.replace('"', "")
    text = text.replace("'", "")

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\.{3,}", "... ", text)
    text = re.sub(r"([.!?])(?=\S)", r"\1 ", text)
    text = re.sub(r"([,;:])(?=\S)", r"\1 ", text)

    return limit_text(text.strip(), MAX_TEXT_CHARS)

def limit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    cut = text[:max_chars]
    last_break = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"), cut.rfind(","))

    if last_break >= 40:
        return cut[:last_break + 1].strip()

    last_space = cut.rfind(" ")
    if last_space > 0:
        return cut[:last_space].strip()

    return cut.strip()


def warmup_tts() -> None:
    global _warmed_up

    if _warmed_up:
        return

    if not is_available():
        print(f"[F5-TTS] referência não encontrada: {REFERENCE_WAV}")
        return

    started_at = time.perf_counter()
    print("[F5-TTS] iniciando warmup")

    get_f5()

    _warmed_up = True
    elapsed = time.perf_counter() - started_at
    print(f"[F5-TTS] warmup concluído em {elapsed:.2f}s")


def generate_audio(text: str) -> tuple[str, np.ndarray] | None:
    if not text or not text.strip():
        return None

    if not is_available():
        print(f"[F5-TTS] referência não encontrada: {REFERENCE_WAV}")
        return None

    normalized_text = normalize_tts_text(text)

    if not normalized_text:
        return None

    output_path = OUTPUT_DIR / f"{uuid.uuid4()}.wav"
    reference_text = get_reference_text()
    device = get_device()
    started_at = time.perf_counter()

    print(f"[F5-TTS] texto: {normalized_text}")
    print(f"[F5-TTS] device: {device}")
    print(f"[F5-TTS] chars: {len(normalized_text)}")
    print(f"[F5-TTS] referência: {REFERENCE_WAV.name} ({REFERENCE_WAV.stat().st_size / 1024:.0f} KB)")

    if not reference_text:
        print("[F5-TTS] aviso: lyra_reference.txt não encontrado, F5 pode usar ASR e ficar mais lento")

    if device == "cuda":
        print(f"[F5-TTS] VRAM antes: {torch.cuda.memory_allocated(0) / 1024**2:.0f} MB")

    f5 = get_f5()

    with _f5_infer_lock:
        wav, sample_rate, _ = f5.infer(
            ref_file=str(REFERENCE_WAV),
            ref_text=reference_text,
            gen_text=normalized_text,
            file_wave=str(output_path),
            seed=None,
            speed=F5_CONFIG["speed"],
            nfe_step=F5_CONFIG["nfe_step"],
            cfg_strength=F5_CONFIG["cfg_strength"],
            sway_sampling_coef=F5_CONFIG["sway_sampling_coef"],
            remove_silence=False,
            show_info=lambda message: print(f"[F5-TTS] {message}"),
            progress=None,
        )

    wav = np.asarray(wav, dtype=np.float32)

    if sample_rate != SAMPLE_RATE:
        try:
            import librosa

            wav = librosa.resample(wav, orig_sr=sample_rate, target_sr=SAMPLE_RATE).astype(np.float32)
            sf.write(str(output_path), wav, SAMPLE_RATE)
            sample_rate = SAMPLE_RATE
        except Exception:
            sf.write(str(output_path), wav, sample_rate)

    if device == "cuda":
        print(f"[F5-TTS] VRAM depois: {torch.cuda.memory_allocated(0) / 1024**2:.0f} MB")

    elapsed = time.perf_counter() - started_at
    print(f"[F5-TTS] áudio gerado em {elapsed:.2f}s: {output_path}")

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
