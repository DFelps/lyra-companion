from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
import json
import time
import uuid

BASE_DIR = Path(__file__).resolve().parents[2]
COMMAND_DIR = BASE_DIR / "data" / "avatar"
COMMAND_PATH = COMMAND_DIR / "commands.json"

COMMAND_DIR.mkdir(parents=True, exist_ok=True)
_lock = Lock()

VALID_COMMANDS = {
    "toggle_microphone",
    "toggle_screen",
    "toggle_listening",
    "start_listening",
    "stop_listening",
    "stop_activity",
    "stop_speaking",
    "set_idle",
    "reload_avatar",
    "noop",
}


@dataclass(frozen=True)
class AvatarCommand:
    id: str
    command: str
    payload: dict
    created_at: float


def _read_raw() -> dict | None:
    if not COMMAND_PATH.is_file():
        return None

    try:
        data = json.loads(COMMAND_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def write_command(command: str, payload: dict | None = None) -> AvatarCommand:
    command = (command or "noop").strip().lower()
    if command not in VALID_COMMANDS:
        command = "noop"

    item = {
        "id": uuid.uuid4().hex,
        "command": command,
        "payload": payload or {},
        "created_at": time.time(),
    }

    with _lock:
        temp_path = COMMAND_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(COMMAND_PATH)

    return AvatarCommand(**item)


class AvatarCommandReader:
    def __init__(self) -> None:
        self._last_seen_id: str | None = None

    def read_next(self) -> AvatarCommand | None:
        with _lock:
            data = _read_raw()

        if not data:
            return None

        command_id = str(data.get("id") or "")
        command_name = str(data.get("command") or "noop").strip().lower()

        if not command_id or command_id == self._last_seen_id:
            return None

        self._last_seen_id = command_id

        if command_name not in VALID_COMMANDS:
            command_name = "noop"

        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        return AvatarCommand(
            id=command_id,
            command=command_name,
            payload=payload,
            created_at=float(data.get("created_at") or time.time()),
        )
