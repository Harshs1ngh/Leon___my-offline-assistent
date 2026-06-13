# memory/memory_manager.py
# Semantic memory disabled until numpy conflict resolved.
# All other features active: context, entity tracking, pronoun resolution,
# structured memory, conversation summarization.

import re
import threading

from memory.context_manager import get_context
from memory.store import (
    append_session_memory,
    get_conversation_history,
    load_memory,
    update_memory,
)

_WORTH_STORING_PATTERNS = [
    (r'\bmy name is\b',                      "personal"),
    (r'\bi (am|work|study|live|prefer)\b',   "personal"),
    (r'\bi (like|love|hate|enjoy|dislike)\b',"preference"),
    (r'\bremember that\b',                   "personal"),
    (r'\bmy (project|app|website|tool)\b',   "project"),
    (r'\bi.m building\b',                    "project"),
    (r'\bi.m working on\b',                  "project"),
    (r'\bmy goal\b',                         "personal"),
    (r'\bi want to\b',                       "personal"),
    (r'\bi need to\b',                       "personal"),
    (r'\b(fixed|solved|broke|deployed|launched|shipped)\b', "event"),
    (r'\b(struggling with|stuck on|problem with)\b',        "event"),
]

_NOISE_PATTERNS = [
    r'^(ok|okay|yes|no|sure|fine|got it|thanks|thank you|alright)$',
    r'^(can you hear me|hello|hi|hey|test)$',
    r'^(what time|what date|open|close|play|search)',
]


def _is_worth_storing(text: str) -> tuple[bool, str]:
    t = text.lower().strip()
    for pattern in _NOISE_PATTERNS:
        if re.search(pattern, t):
            return False, ""
    for pattern, category in _WORTH_STORING_PATTERNS:
        if re.search(pattern, t):
            return True, category
    return False, ""


def _extract_structured_facts(text: str) -> dict:
    facts = {}
    t = text.lower().strip()

    name_match = re.search(r'my name is (\w+)', t)
    if name_match:
        facts["personal.name"] = name_match.group(1).capitalize()

    work_match = re.search(r'i (?:work|study) (?:at|as|in) (.+?)(?:\.|$)', t)
    if work_match:
        facts["personal.work"] = work_match.group(1).strip()

    project_match = re.search(
        r'(?:my|i.m building|i.m working on) (?:project|app|tool|website|system) (?:called|named|is)? ?(\w+)', t
    )
    if project_match:
        facts[f"projects.{project_match.group(1)}"] = text

    return facts


def _summarize_conversation(turns: list[dict]) -> str:
    if not turns:
        return ""
    try:
        from brain.engines.ollama_engine import generate
        history_text = "\n".join(
            f"User: {t['content']}" if t["role"] == "user"
            else f"Leon: {t['content']}"
            for t in turns[:20]
        )
        summary = generate(
            f"Summarize this conversation in 2-3 sentences, preserving key facts:\n{history_text}",
            system_prompt="You summarize conversations. Be concise. Preserve names, projects, and key facts.",
            max_tokens=80,
        ).strip()
        return summary
    except Exception:
        return ""


def process_turn(user_input: str, leon_reply: str):
    """Called after every turn. Updates context and stores structured facts."""
    def _store():
        ctx = get_context()
        ctx.add_turn(user_input, leon_reply)

        facts = _extract_structured_facts(user_input)
        for key, val in facts.items():
            update_memory(key, val)

        append_session_memory(user_input, leon_reply)

    threading.Thread(target=_store, daemon=True, name="memory-store").start()


def build_prompt_context(user_input: str) -> str:
    """Builds compact context block for LLM prompt."""
    ctx    = get_context()
    memory = load_memory()
    parts  = []

    # Pronoun resolution
    resolved_input = ctx.resolve_pronouns_in_text(user_input)
    if resolved_input != user_input:
        parts.append(f"[Resolved query: {resolved_input}]")

    # Live context — entities, topic, tone, recent turns
    ctx_block = ctx.get_context_block()
    if ctx_block:
        parts.append(ctx_block)

    # Structured memory — personal facts
    personal = memory.get("personal", {})
    if personal:
        facts = ", ".join(f"{k}: {v}" for k, v in personal.items() if v)
        if facts:
            parts.append(f"Known about user: {facts}")

    # Active projects
    projects = memory.get("projects", {})
    if projects:
        parts.append(f"User's projects: {', '.join(projects.keys())}")

    return "\n".join(parts)


def get_resolved_input(user_input: str) -> str:
    return get_context().resolve_pronouns_in_text(user_input)


def get_conversation_context(n: int = 6) -> list[dict]:
    ctx       = get_context()
    all_turns = ctx.get_recent_turns(n=30)

    if len(all_turns) > 24:
        old_turns = all_turns[:-12]
        recent    = all_turns[-12:]
        summary   = _summarize_conversation(old_turns)
        if summary:
            return [
                {"role": "system", "content": f"[Earlier conversation summary: {summary}]"},
                *recent,
            ]

    return ctx.get_recent_turns(n=n)
