from queue import Queue
from threading import Thread, Event, Lock
import time

from app.brain.memory_manager import MemoryManager
from app.brain.persona_loader import PersonaLoader
from app.brain.style_guard import StyleGuard
from app.brain.behavior import is_repeated_question, is_aggressive
from app.core.response_builder import ResponseBuilder
from app.core.router import Router
from app.core.safety import Safety
from app.core.session_manager import SessionManager
from app.llm.general_reasoner import GeneralReasoner
from app.memory.retrieval import Retrieval
from app.ui.cli import CLI
from app.avatar.state import choose_expression, set_mode
from app.utils.logger import log
from app.voice.tts import configure_tts, generate_audio, warmup_tts
from app.avatar.lipsync import play_with_lipsync


class LyraOrchestrator:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.persona = PersonaLoader().load()
        model_name = config.get("models", {}).get("general", {}).get("name", "llama3.1:8b")
        self.reasoner = GeneralReasoner(persona=self.persona, model=model_name)
        self.router = Router()
        self.retrieval = Retrieval()
        self.memory = MemoryManager()
        self.style_guard = StyleGuard()
        self.response_builder = ResponseBuilder()
        self.safety = Safety()
        self.session = SessionManager()
        self.cli = CLI()

        self.voice_enabled = config.get("voice", {}).get("tts", {}).get("enabled", False)
        configure_tts(config.get("voice", {}))

        self.voice_text_queue: Queue[str | None] = Queue()
        self.voice_audio_queue: Queue[tuple[str, object] | None] = Queue()

        self.voice_state_lock = Lock()
        self.pending_voice_items = 0
        self.voice_active = Event()

        self.voice_generate_thread = Thread(target=self._voice_generate_worker, daemon=True)
        self.voice_play_thread = Thread(target=self._voice_play_worker, daemon=True)

        self.voice_generate_thread.start()
        self.voice_play_thread.start()

        if self.voice_enabled:
            Thread(target=self._warmup_voice, daemon=True).start()

    def _warmup_voice(self) -> None:
        try:
            warmup_tts()
        except Exception as exc:
            log(f"Falha no warmup TTS: {exc}")

    def _mark_voice_item_added(self) -> None:
        with self.voice_state_lock:
            self.pending_voice_items += 1
            self.voice_active.set()

    def _mark_voice_item_finished(self) -> None:
        with self.voice_state_lock:
            if self.pending_voice_items > 0:
                self.pending_voice_items -= 1

            if self.pending_voice_items == 0:
                self.voice_active.clear()

    def _set_state_safe(self, state: str, expression: str | None = None) -> None:
        try:
            set_mode(state, expression=expression)
        except Exception as exc:
            log(f"Falha ao ativar estado '{state}': {exc}")

    def _voice_generate_worker(self) -> None:
        while True:
            text = self.voice_text_queue.get()

            if text is None:
                self.voice_audio_queue.put(None)
                self.voice_text_queue.task_done()
                break

            try:
                result = generate_audio(text)
                if result is not None:
                    _, wav = result
                    expression = choose_expression("", text)
                    self.voice_audio_queue.put((expression, wav))
                else:
                    self._mark_voice_item_finished()
            except Exception as exc:
                log(f"Falha ao gerar TTS: {exc}")
                self._mark_voice_item_finished()
            finally:
                self.voice_text_queue.task_done()

    def _voice_play_worker(self) -> None:
        while True:
            item = self.voice_audio_queue.get()

            if item is None:
                self.voice_audio_queue.task_done()
                break

            try:
                expression, wav = item
                play_with_lipsync(wav, 24000, expression=expression)
            except Exception as exc:
                log(f"Falha ao reproduzir áudio com lipsync: {exc}")
            finally:
                self._mark_voice_item_finished()
                self.voice_audio_queue.task_done()

    def _enqueue_voice(self, text: str) -> None:
        if not self.voice_enabled:
            return

        cleaned = text.strip()
        if not cleaned:
            return

        self._mark_voice_item_added()
        self.voice_text_queue.put(cleaned)

    def _wait_until_voice_finishes(self) -> None:
        if not self.voice_enabled:
            return

        showed_status = False

        while self.voice_active.is_set():
            if not showed_status:
                print("Lyra falando...", end="\r", flush=True)
                showed_status = True
            time.sleep(0.15)

        if showed_status:
            print(" " * 40, end="\r", flush=True)

        self._set_state_safe("idle")

    def _prepare_input(self, user_text: str) -> tuple[dict | None, str | None, str | None]:
        safety_message = self.safety.validate(user_text)
        if safety_message:
            payload = self.response_builder.build(safety_message)
            self.memory.remember_exchange(user_text, payload["text"])
            return payload, None, None

        route = self.router.classify(user_text)
        context = self.retrieval.build_context()

        history = self.memory.get_last_user_messages()
        repeated = is_repeated_question(user_text, history)
        aggressive = is_aggressive(user_text)

        modified_input = user_text

        if repeated:
            modified_input = (
                "O usuário repetiu a mesma pergunta. "
                "Responda de forma diferente ou mais curta.\n\n"
                + modified_input
            )

        if aggressive:
            modified_input = (
                "O usuário está sendo agressivo. "
                "Responda de forma calma, curta e levemente fria, sem confrontar.\n\n"
                + modified_input
            )

        if route == "light_technical":
            modified_input = (
                "Responda de forma leve e geral, sem aprofundar em detalhes técnicos. "
                + modified_input
            )

        return None, modified_input, context

    def process_text(self, user_text: str) -> dict:
        immediate_payload, modified_input, context = self._prepare_input(user_text)
        if immediate_payload is not None:
            return immediate_payload

        raw_answer = self.reasoner.answer(user_text=modified_input, context=context)

        last_answer = self.memory.get_last_answer()
        if last_answer and raw_answer.strip() == last_answer.strip():
            raw_answer = "Já respondi isso de outra forma."

        safe_answer = self.style_guard.enforce(raw_answer)
        payload = self.response_builder.build(safe_answer)

        self.memory.remember_exchange(user_text, payload["text"])

        return payload

    def run_cli(self) -> None:
        log("Lyra iniciada.")
        self.cli.print_banner(self.persona.get("name", "Lyra"))
        self._set_state_safe("idle")

        while True:
            self._wait_until_voice_finishes()

            user_text = self.cli.read_input()

            if user_text.lower() in {"sair", "exit", "quit"}:
                log("Encerrando Lyra.")
                self.voice_text_queue.put(None)
                self.voice_text_queue.join()
                self.voice_audio_queue.join()
                self._set_state_safe("idle")
                break

            immediate_payload, modified_input, context = self._prepare_input(user_text)

            if immediate_payload is not None:
                self.cli.show_response(immediate_payload["text"])
                expression = choose_expression(user_text, immediate_payload["text"])
                self._set_state_safe("speaking", expression=expression)
                self._enqueue_voice(immediate_payload["text"])
                continue

            self._set_state_safe("thinking", expression=choose_expression(user_text))
            print("Lyra: ", end="", flush=True)

            chunks = []

            try:
                for chunk in self.reasoner.stream_answer(user_text=modified_input, context=context):
                    if not chunk:
                        continue

                    print(chunk, end="", flush=True)
                    chunks.append(chunk)

                print()

                raw_answer = "".join(chunks).strip()
                if not raw_answer:
                    raw_answer = "Não consegui responder agora."

                last_answer = self.memory.get_last_answer()
                if last_answer and raw_answer.strip() == last_answer.strip():
                    raw_answer = "Já respondi isso de outra forma."

                safe_answer = self.style_guard.enforce(raw_answer)
                payload = self.response_builder.build(safe_answer)

                expression = choose_expression(user_text, payload["text"])
                self._set_state_safe("speaking", expression=expression)
                self.memory.remember_exchange(user_text, payload["text"])
                self._enqueue_voice(payload["text"])

                if not self.voice_enabled:
                    self._set_state_safe("idle")

            except Exception as exc:
                print()
                log(f"Falha no streaming do LLM: {exc}")
                payload = self.process_text(user_text)
                self.cli.show_response(payload["text"])
                self._enqueue_voice(payload["text"])

                if not self.voice_enabled:
                    self._set_state_safe("idle")

