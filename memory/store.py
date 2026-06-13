# memory/store.py
import json
import os
import time
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "leon_memory.json")
MEMORY_FILE = os.path.normpath(MEMORY_FILE)

_DEFAULT = {
    "personal": {}, "preferences": {}, "long_term": {},
    "projects": {}, "session_memory": [], "conversation_log": [],
    "session": {}, "mode": "normal", "last_updated": "",
}


def _clean(data):
    if not isinstance(data, dict):
        return data
    return {k.strip(): _clean(v) for k, v in data.items()}


def load_memory() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return dict(_DEFAULT)
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = _clean(json.load(f))
    except Exception:
        return dict(_DEFAULT)
    for k, v in _DEFAULT.items():
        if k not in data:
            data[k] = v
    return data


def save_memory(memory: dict):
    memory["last_updated"] = datetime.now().isoformat()
    tmp = MEMORY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)
    os.replace(tmp, MEMORY_FILE)


def update_memory(dot_key: str, value):
    memory = load_memory()
    keys   = dot_key.split(".")
    ref    = memory
    for k in keys[:-1]:
        k = k.strip()
        if k not in ref or not isinstance(ref[k], dict):
            ref[k] = {}
        ref = ref[k]
    ref[keys[-1].strip()] = value
    save_memory(memory)


def append_session_memory(user_input: str, reply: str):
    memory = load_memory()
    entry  = {"timestamp": time.time(), "user": user_input, "leon": reply}
    last   = memory["session_memory"][-1] if memory["session_memory"] else None
    if last:
        if (last["user"].strip().lower() == user_input.strip().lower()
                and (time.time() - last["timestamp"]) < 2):
            return
    memory["session_memory"]   = (memory["session_memory"] + [entry])[-50:]
    memory["conversation_log"] = (memory["conversation_log"] + [entry])[-200:]
    save_memory(memory)


def get_conversation_history(n: int = 6) -> list[dict]:
    memory  = load_memory()
    recent  = memory.get("session_memory", [])[-n:]
    messages = []
    for turn in recent:
        messages.append({"role": "user",      "content": turn["user"]})
        messages.append({"role": "assistant",  "content": turn["leon"]})
    return messages


def auto_learn_fact(text: str) -> str | None:
    memory = load_memory()
    t      = text.lower().strip()

    if "my name is" in t:
        try:
            name = t.split("my name is")[-1].strip().split()[0].capitalize()
            memory["personal"]["name"] = name
            save_memory(memory)
            return f"Got it, sir. I'll remember your name is {name}."
        except Exception:
            pass

    if t.startswith("remember that "):
        fact = t[14:].strip()
        if fact:
            key = " ".join(fact.split()[:4])
            memory["long_term"][key] = fact
            save_memory(memory)
            return "Remembered, sir."

    for phrase in ("i work at ", "i work as "):
        if t.startswith(phrase):
            info = t[len(phrase):].strip()
            memory["personal"]["work"] = info
            save_memory(memory)
            return "Noted, sir."

    return None


def auto_recall_answer(text: str) -> str | None:
    memory = load_memory()
    t      = text.lower().strip()

    if "what is my name" in t or "do you know my name" in t:
        name = memory.get("personal", {}).get("name")
        return f"Your name is {name}, sir." if name else None

    if any(p in t for p in ("what do you remember", "what do you know about me")):
        facts = {**memory.get("personal", {}), **memory.get("long_term", {})}
        if facts:
            return "I remember: " + ", ".join(f"{k}: {v}" for k, v in facts.items() if v) + ", sir."
        return "I don't have much stored yet, sir."

    if "last conversation" in t or "what did we talk about" in t:
        log = memory.get("conversation_log", [])[-5:]
        if not log:
            return "Nothing stored from before, sir."
        return "Recently: " + " | ".join(x["user"][:40] for x in log) + "."

    for key, val in memory.get("long_term", {}).items():
        if key.lower() in t:
            return str(val)

    return None


def load_session_into_context():
    try:
        from memory.context_manager import get_context
        memory = load_memory()
        ctx    = get_context()
        recent = memory.get("conversation_log", [])[-10:]
        for turn in recent:
            ctx.add_turn(turn["user"], turn["leon"])
        if recent:
            print(f"✅ Memory: loaded {len(recent)} turns from last session")
    except Exception as e:
        print(f"⚠️  Session restore failed: {e}")
