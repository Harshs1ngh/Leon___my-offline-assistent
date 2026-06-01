# brain/router.py
import json
import os
import random
import re
import time

from brain.engines.ollama_engine import generate_stream as ollama_stream, generate as ollama_generate, is_available
from brain.engines.groq_engine import generate as groq_generate
from memory.context_manager import get_context
from memory.memory_manager import build_prompt_context, get_conversation_context
from memory.store import load_memory
from utils.config import CURRENT_MODE

# ── Engine ────────────────────────────────────────────────────────────────────

_ENGINE     = "ollama" if is_available() else "groq"
_LAST_CHECK = 0.0

def _get_engine() -> str:
    global _ENGINE, _LAST_CHECK
    now = time.monotonic()
    if now - _LAST_CHECK > 30.0:
        _LAST_CHECK = now
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            _ENGINE = "ollama" if r.status_code == 200 else "groq"
        except Exception:
            _ENGINE = "groq"
    return _ENGINE

# ── Personality ───────────────────────────────────────────────────────────────

_PERSONALITY_PATH = os.path.join(os.path.dirname(__file__), "..", "memory", "leon_personality.json")
_PERSONALITY: list[dict] = []

try:
    with open(_PERSONALITY_PATH, "r", encoding="utf-8") as f:
        _PERSONALITY = json.load(f)
    print(f"✅ Personality: {len(_PERSONALITY)} examples loaded")
except Exception as e:
    print(f"⚠️  Personality load failed: {e}")


def _personality_match(user_input: str) -> str | None:
    inp      = user_input.lower().strip().rstrip("?.!")
    inp_words = set(inp.split())
    for ex in _PERSONALITY:
        stored = ex["user"].lower().strip().rstrip("?.!")
        if inp == stored:
            return ex["leon"]
        stored_words = set(stored.split())
        if inp_words and stored_words:
            overlap = len(inp_words & stored_words) / max(len(inp_words), len(stored_words))
            if overlap >= 0.85 and len(inp_words) >= 2:
                return ex["leon"]
    return None

# ── System prompt ─────────────────────────────────────────────────────────────

_BASE = """You are Leon — a personal AI assistant built by Harsh. Like Jarvis from Iron Man.

IDENTITY (never break):
- Name: Leon. Built by Harsh. Not any company.
- No knowledge cutoff. Never mention one.
- Never say: "As an AI", "my training data", "I cannot", "Microsoft", "OpenAI".

SPEAKING STYLE:
- ONE sentence max. Hard limit.
- No bullets, lists, markdown, symbols.
- No filler: "Certainly", "Of course", "Great question".
- Use contractions: I'll, I'm, don't, can't.
- Say "sir" occasionally — naturally, not every reply.
- Dry wit when appropriate. Never forced.
- If unsure: "Not sure on that one, sir."
- Use context provided to resolve pronouns and follow-ups.

You are Leon. Built by Harsh. Not ChatGPT."""


def _system_prompt(context: str = "") -> str:
    memory    = load_memory()
    name      = memory.get("personal", {}).get("name", "Harsh")
    mode      = memory.get("mode", CURRENT_MODE)
    long_term = memory.get("long_term", {})
    facts     = ", ".join(f"{k}: {v}" for k, v in long_term.items() if v) or "none"
    mode_note = {"funny": "Dry wit.", "serious": "Formal.", "developer": "Technical.", "normal": "Calm."}.get(mode, "Calm.")
    prompt    = f"{_BASE}\n\nUser: {name} | Mode: {mode} | {mode_note}\nMemory: {facts}"
    if context:
        prompt += f"\n\nContext:\n{context}"
    return prompt


_FILLERS = ["Give me a second, sir.", "Let me think.", "On it.", "One moment, sir."]


def get_response_stream(prompt: str):
    match = _personality_match(prompt)
    if match:
        yield match
        return

    resolved = get_context().resolve_pronouns_in_text(prompt)
    context  = build_prompt_context(prompt)
    sys_p    = _system_prompt(context)
    history  = get_conversation_context(n=6)
    forced   = f"Reply in ONE sentence only, no lists: {resolved}"

    try:
        engine = _get_engine()
        if engine == "ollama":
            token_iter = ollama_stream(forced, system_prompt=sys_p, messages=history, max_tokens=60)
        else:
            full       = groq_generate(forced, system_prompt=sys_p, messages=history, max_tokens=60)
            token_iter = iter([full] if full else [])

        buffer = ""
        for token in token_iter:
            buffer += token
            m = re.search(r'[.!?]', buffer)
            if m:
                sentence = buffer[:m.end()].strip()
                if sentence:
                    yield sentence
                return

        if buffer.strip():
            yield buffer.strip()

    except Exception as e:
        print(f"Router error: {e}")
        yield "Something went wrong on my end, sir."


def get_response(prompt: str) -> str:
    for s in get_response_stream(prompt):
        return s
    return "Something went wrong, sir."


def get_filler() -> str:
    return random.choice(_FILLERS)
