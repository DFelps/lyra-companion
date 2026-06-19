from __future__ import annotations

from pathlib import Path
from threading import Lock
import json
import time

BASE_DIR = Path(__file__).resolve().parents[2]
STATE_DIR = BASE_DIR / "data" / "avatar"
STATE_PATH = STATE_DIR / "state.json"

STATE_DIR.mkdir(parents=True, exist_ok=True)
_lock = Lock()

DEFAULT_STATE = {
    "mode": "idle",
    "eye": "open",
    "mouth": "closed",
    "expression": "neutral",
    "speaking": False,
    "mouth_level": 0,
    "text": "",
    "updated_at": 0,
}


def _load() -> dict:
    if not STATE_PATH.is_file():
        return DEFAULT_STATE.copy()

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {**DEFAULT_STATE, **data}
    except Exception:
        return DEFAULT_STATE.copy()


def set_avatar_state(**changes) -> None:
    with _lock:
        state = _load()
        state.update({key: value for key, value in changes.items() if value is not None})
        state["updated_at"] = time.time()

        temp_path = STATE_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(STATE_PATH)


def set_mode(mode: str, expression: str | None = None) -> None:
    values = {"mode": mode}

    if mode == "idle":
        values.update({"speaking": False, "mouth_level": 0, "mouth": "closed"})
    elif mode == "thinking":
        values.update({"speaking": False, "mouth_level": 0, "mouth": "closed", "eye": "serious"})
    elif mode == "speaking":
        values.update({"speaking": True})

    if expression is not None:
        values["expression"] = expression
        values.update(expression_to_layers(expression))

    set_avatar_state(**values)


def set_mouth_level(level: int) -> None:
    level = max(0, min(3, int(level)))
    mouth = "closed"

    if level == 1:
        mouth = "middle_open"
    elif level == 2:
        mouth = "open"
    elif level >= 3:
        mouth = "surprise"

    set_avatar_state(mode="speaking", speaking=True, mouth_level=level, mouth=mouth)


def expression_to_layers(expression: str) -> dict:
    if expression == "happy":
        return {"eye": "happy", "mouth": "smile"}

    if expression == "serious":
        return {"eye": "serious", "mouth": "closed"}

    if expression == "surprised":
        return {"eye": "open", "mouth": "surprise"}

    return {"eye": "open", "mouth": "closed"}


def choose_expression(user_text: str, answer_text: str | None = None) -> str:
    text = f"{user_text} {answer_text or ''}".lower()

    happy_words = ["obrigado", "obrigada", "valeu", "boa", "kkk", "haha", "feliz", "legal", "perfeito"]
    surprise_words = ["caramba", "vish", "nossa", "sério", "surpresa", "bugou", "erro", "deu ruim"]
    serious_words = ["erro", "problema", "bug", "falha", "investigar", "segurança", "produção", "servidor", "código"]

    if any(word in text for word in happy_words):
        return "happy"

    if any(word in text for word in surprise_words):
        return "surprised"

    if any(word in text for word in serious_words) or "?" in user_text:
        return "serious"

    return "neutral"


set_avatar_state()
