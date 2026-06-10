# main.py — Leon AI Assistant
# STT: Google (primary) → Whisper (fallback)
# TTS: Edge-TTS Andrew (primary) → Kokoro (fallback)
# LLM: Ollama gemma2:2b → Groq fallback

import random
import sys
import threading
import time

import keyboard
import numpy as np
import sounddevice as sd
import speech_recognition as sr

from brain.router import get_response_stream, get_filler
from memory.store import load_session_into_context, load_memory, update_memory
from memory.context_manager import get_context
from memory.memory_manager import process_turn
from skills.dispatcher import dispatch
from utils.config import set_mode
from utils.text_normalizer import normalize_for_tts
from voice.tts import say, stop_speaking, is_speaking

# ── STT setup ─────────────────────────────────────────────────────────────────

_recognizer = sr.Recognizer()
_recognizer.energy_threshold        = 300
_recognizer.dynamic_energy_threshold = True

_whisper = None
def _load_whisper():
    global _whisper
    try:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel("base", device="cpu", compute_type="int8")
        print("✅ STT: Google (primary) + Whisper base (fallback)")
    except Exception:
        print("✅ STT: Google Speech Recognition")

_load_whisper()
load_session_into_context()

# ── Mic settings ──────────────────────────────────────────────────────────────

SAMPLE_RATE    = 16000
CHANNELS       = 1
SILENCE_THRESH = 0.012
SILENCE_AFTER  = 0.6
MAX_PHRASE     = 10.0
MIN_PHRASE     = 0.3

# ── Wake words ────────────────────────────────────────────────────────────────

WAKE_WORDS = {"leon", "le on", "leo", "eon", "lean", "lien", "neon"}

WAKE_MESSAGES = [
    "Leon online. Ready when you are.",
    "All systems active. What do you need?",
    "Leon here. Go ahead.",
    "Fully operational. Standing by.",
]

SHUTDOWN_MESSAGES = [
    "Leon powering down. Until next time.",
    "Going offline. Take care.",
    "Signing out. See you soon.",
]

# ── Shared state ──────────────────────────────────────────────────────────────

_running         = threading.Event()
_running.set()
_last_input_time = time.monotonic()
_last_input_lock = threading.Lock()
_processing      = threading.Event()


def _touch():
    global _last_input_time
    with _last_input_lock:
        _last_input_time = time.monotonic()


def _idle_seconds():
    with _last_input_lock:
        return time.monotonic() - _last_input_time


# ── Shutdown ──────────────────────────────────────────────────────────────────

def _shutdown(reason=""):
    if reason:
        print(f"\nShutting down: {reason}")
    stop_speaking()
    say(random.choice(SHUTDOWN_MESSAGES))
    deadline = time.monotonic() + 5.0
    while is_speaking() and time.monotonic() < deadline:
        time.sleep(0.05)
    _running.clear()


def _hotkey_thread():
    keyboard.wait("ctrl+shift+l")
    _shutdown("Hotkey pressed.")


def _idle_thread():
    idle_prompts = [
        "Still here, sir. Say Leon if you need me.",
        "Standing by. Ready when you are.",
        "Systems idle. Just checking in, sir.",
    ]
    while _running.is_set():
        time.sleep(5)
        if _idle_seconds() < 300 or is_speaking() or _processing.is_set():
            continue
        msg = random.choice(idle_prompts)
        print(f"\nLeon (idle): {msg}")
        say(msg)
        _touch()


# ── Transcribe ────────────────────────────────────────────────────────────────

def _transcribe_google(audio_np: np.ndarray) -> str:
    try:
        audio_int16 = (audio_np * 32767).astype(np.int16)
        audio_data  = sr.AudioData(
            audio_int16.tobytes(),
            sample_rate=SAMPLE_RATE,
            sample_width=2,
        )
        return _recognizer.recognize_google(audio_data).lower().strip()
    except sr.UnknownValueError:
        return ""
    except Exception:
        return ""


def _transcribe_whisper(audio_np: np.ndarray) -> str:
    if _whisper is None:
        return ""
    try:
        segments, _ = _whisper.transcribe(
            audio_np, language="en", beam_size=1,
            best_of=1, temperature=0.0, vad_filter=True,
        )
        return " ".join(s.text for s in segments).strip().lower()
    except Exception:
        return ""


def _transcribe(audio_np: np.ndarray) -> str:
    text = _transcribe_google(audio_np)
    if not text and _whisper:
        text = _transcribe_whisper(audio_np)
    return text


# ── Command processor ─────────────────────────────────────────────────────────

def _process_command(command: str):
    _processing.set()
    try:
        cmd = command.strip().lower().rstrip(".,!?")

        # Shutdown
        shutdown_words = (
            "shutdown", "shut down", "shoutdown", "turn off",
            "power off", "go offline", "exit", "quit", "bye leon",
        )
        if any(w in cmd for w in shutdown_words):
            _shutdown("Voice command.")
            return

        # Mode switching
        modes = {
            "funny mode": "funny", "serious mode": "serious",
            "normal mode": "normal", "developer mode": "developer",
            "dev mode": "developer",
        }
        for phrase, mode in modes.items():
            if phrase in cmd:
                set_mode(mode)
                update_memory("mode", mode)
                say(f"Switched to {mode} mode, sir.")
                return

        # Skill dispatch
        result = dispatch(cmd)
        if result is not None:
            if result:
                print(f"\nLeon: {result}")
                needs_speech = any(w in result.lower() for w in (
                    "couldn't", "failed", "not found", "error",
                    "can't", "unable", "clarify", "what do you mean",
                    "done", "opened", "closed", "set", "saved",
                ))
                if needs_speech:
                    say(normalize_for_tts(result))
            process_turn(command, result or "Done.")
            return

        # LLM response
        memory = load_memory()
        mode   = memory.get("mode", "normal")
        prompt = command
        if mode == "funny":
            prompt = "Respond humorously in one sentence: " + command
        elif mode == "serious":
            prompt = "Respond seriously in one sentence: " + command
        elif mode == "developer":
            prompt = "Respond with technical precision in one sentence: " + command

        full_reply = []
        for sentence in get_response_stream(prompt):
            s = normalize_for_tts(sentence.strip())
            if s:
                full_reply.append(s)
                say(s)

        reply = " ".join(full_reply)
        if reply:
            print(f"\nLeon: {reply}")
            update_memory("session.last_input", command)
            update_memory("session.last_response", reply)
            process_turn(command, reply)

    except Exception as e:
        import traceback
        traceback.print_exc()
        say("Something went wrong on my end, sir.")
    finally:
        _processing.clear()


# ── Persistent mic loop ───────────────────────────────────────────────────────

def _listen_loop():
    print("Mic loop started.")
    say(random.choice(WAKE_MESSAGES))
    deadline = time.monotonic() + 5.0
    while is_speaking() and time.monotonic() < deadline:
        time.sleep(0.05)

    chunk = int(SAMPLE_RATE * 0.1)
    state = {"silent": 0.0, "frames": [], "active": False, "total": 0.0}

    def _cb(indata, *_):
        if is_speaking():
            state["frames"] = []
            state["silent"] = 0.0
            state["active"] = False
            state["total"]  = 0.0
            return

        data = indata.copy().flatten()
        rms  = float(np.sqrt(np.mean(data ** 2)))

        if rms > SILENCE_THRESH:
            state["silent"] = 0.0
            state["active"] = True
            state["total"] += 0.1
            state["frames"].append(data)
            if is_speaking():
                stop_speaking()
        else:
            if state["active"]:
                state["frames"].append(data)
                state["silent"] += 0.1
                state["total"]  += 0.1
                if state["silent"] >= SILENCE_AFTER or state["total"] >= MAX_PHRASE:
                    audio          = np.concatenate(state["frames"]).flatten()
                    state["frames"] = []
                    state["silent"] = 0.0
                    state["active"] = False
                    state["total"]  = 0.0
                    if len(audio) / SAMPLE_RATE >= MIN_PHRASE:
                        threading.Thread(
                            target=_handle, args=(audio,),
                            daemon=True, name="transcribe"
                        ).start()

    def _handle(audio):
        text = _transcribe(audio)
        if not text or len(text.split()) < 1:
            return

        words      = text.strip().split()
        first_word = words[0].lower().rstrip(".,!?")

        if first_word in WAKE_WORDS:
            command = " ".join(words[1:]).strip()
            if not command:
                say("Yes? Go ahead, sir.")
                _touch()
                return
        else:
            command = text.strip()

        if _processing.is_set():
            stop_speaking()

        print(f"\nYou: {command}")
        _touch()
        threading.Thread(
            target=_process_command, args=(command,),
            daemon=True, name="cmd"
        ).start()

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS,
            dtype="float32", blocksize=chunk, callback=_cb,
        ):
            while _running.is_set():
                time.sleep(0.1)
    except Exception as e:
        print(f"Mic error: {e}")


# ── Text input ────────────────────────────────────────────────────────────────

def _text_loop():
    while _running.is_set():
        try:
            command = input("\nYou (text): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not command:
            continue
        if command.lower() in ("exit", "quit", "shutdown"):
            _shutdown("Text shutdown.")
            break
        if _processing.is_set():
            stop_speaking()
        print(f"You: {command}")
        _touch()
        threading.Thread(
            target=_process_command, args=(command,),
            daemon=True, name="cmd"
        ).start()
        while _processing.is_set() or is_speaking():
            time.sleep(0.1)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Leon is online. Press Ctrl+Shift+L to shut down.")
    print("Speak English or type below.\n")

    threading.Thread(target=_hotkey_thread, daemon=True).start()
    threading.Thread(target=_idle_thread,   daemon=True).start()
    threading.Thread(target=_listen_loop,   daemon=True).start()

    try:
        _text_loop()
    except KeyboardInterrupt:
        _shutdown("KeyboardInterrupt.")

    print("\nLeon is offline.")
    sys.exit(0)
