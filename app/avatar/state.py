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

VALID_MODES = {"idle", "thinking", "listening", "speaking", "approach"}
VALID_EXPRESSIONS = {"neutral", "serious", "happy", "surprised"}

DEFAULT_CONTROLS = {
    "microphone": False,
    "screen": False,
    "listening": False,
}

DEFAULT_STATE = {
    "mode": "idle",
    "pose": None,
    "eye": "open",
    "mouth": "closed",
    "expression": "neutral",
    "speaking": False,
    "mouth_level": 0,
    "text": "",
    "controls": DEFAULT_CONTROLS.copy(),
    "updated_at": 0,
}


def _merge_state(data: dict | None) -> dict:
    state = {**DEFAULT_STATE, **(data or {})}

    controls = state.get("controls")
    if not isinstance(controls, dict):
        controls = {}

    state["controls"] = {**DEFAULT_CONTROLS, **controls}
    return state


def _load() -> dict:
    if not STATE_PATH.is_file():
        return _merge_state(None)

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _merge_state(None)
        return _merge_state(data)
    except Exception:
        return _merge_state(None)


def get_avatar_state() -> dict:
    with _lock:
        return _load()


def _normalize_mode(mode: str | None) -> str:
    value = (mode or "idle").strip().lower()
    return value if value in VALID_MODES else "idle"


def _normalize_expression(expression: str | None) -> str:
    value = (expression or "neutral").strip().lower()
    return value if value in VALID_EXPRESSIONS else "neutral"


def _write_state(state: dict) -> None:
    temp_path = STATE_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(STATE_PATH)


def set_avatar_state(**changes) -> None:
    with _lock:
        state = _load()

        for key, value in changes.items():
            if value is None:
                continue

            if key == "controls" and isinstance(value, dict):
                state["controls"] = {**DEFAULT_CONTROLS, **state.get("controls", {}), **value}
            else:
                state[key] = value

        state["updated_at"] = time.time()
        _write_state(_merge_state(state))


def set_controls(**controls: bool) -> None:
    cleaned = {key: bool(value) for key, value in controls.items() if key in DEFAULT_CONTROLS}
    if cleaned:
        set_avatar_state(controls=cleaned)


def set_mode(mode: str, expression: str | None = None, pose: str | None = None) -> None:
    mode = _normalize_mode(mode)
    expression = _normalize_expression(expression)

    current_controls = _load().get("controls", DEFAULT_CONTROLS.copy())

    values = {
        "mode": mode,
        "expression": expression,
    }

    if pose is not None:
        values["pose"] = pose
    elif mode in {"thinking", "listening", "approach"}:
        values["pose"] = None

    if mode == "idle":
        values.update({
            "speaking": False,
            "mouth_level": 0,
            "mouth": "closed",
            "controls": {**current_controls, "listening": False},
            **expression_to_layers(expression),
        })
    elif mode == "thinking":
        # Thinking should look quiet, not like speech/lipsync.
        values.update({
            "speaking": False,
            "mouth_level": 0,
            "eye": "closed",
            "mouth": "closed",
            "controls": {**current_controls, "listening": False},
        })
    elif mode == "listening":
        values.update({
            "speaking": False,
            "mouth_level": 0,
            "eye": "open",
            "mouth": "closed",
            "controls": {**current_controls, "listening": True},
        })
    elif mode == "approach":
        values.update({
            "speaking": False,
            "mouth_level": 0,
            "eye": "open",
            "mouth": "closed",
            "controls": {**current_controls, "listening": False},
        })
    elif mode == "speaking":
        values.update({
            "speaking": True,
            "controls": {**current_controls, "listening": False},
            **expression_to_layers(expression),
        })

    set_avatar_state(**values)


def set_mouth_level(level: int) -> None:
    level = max(0, min(3, int(level)))

    if level <= 0:
        mouth = "closed"
    elif level == 1:
        mouth = "middle_open"
    else:
        # Keep surprise as an expression, not as normal speech lipsync.
        mouth = "open"

    set_avatar_state(mode="speaking", speaking=True, mouth_level=level, mouth=mouth)


def expression_to_layers(expression: str) -> dict:
    expression = _normalize_expression(expression)

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
