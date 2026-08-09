# skills/dispatcher.py
import re
import threading
from skills.system.desktop import (
    open_app, close_app, take_screenshot, set_volume_up, set_volume_down,
    mute_volume, set_brightness_up, set_brightness_down, get_cpu, get_ram,
    get_battery, get_disk, get_time, get_date, shutdown_after,
)
from skills.browser.browser import (
    open_url, google_search, open_youtube, youtube_search,
    close_browser_tab, pause_video,
)
from skills.files.files import find_file, open_file, list_files
from skills.focus.focus import start_focus, stop_focus, get_focus_status
from skills.schedule.scheduler import set_timer, set_reminder, get_reminders
from skills.tasks.executor import execute_task


# ── Fuzzy resolver ────────────────────────────────────────────────────────────

def _fuzzy_resolve(cmd: str) -> str | None:
    try:
        from brain.engines.ollama_engine import generate
        result = generate(
            f'User said to voice assistant: "{cmd}"\n'
            f'Fix typos/mishearings. Return ONLY the corrected command in lowercase.\n'
            f'If unclear, reply: unclear',
            system_prompt="Fix voice command typos. Output only corrected command or 'unclear'.",
            max_tokens=12,
        ).strip().lower()
        return None if result in ("unclear", cmd, "") else result
    except Exception:
        return None


# ── Main dispatch ─────────────────────────────────────────────────────────────

def dispatch(cmd: str, _depth: int = 0) -> str | None:
    cmd = cmd.strip().lower().rstrip(".,!?")

    # ── Resolve "it/that" pronouns to last opened app ─────────────────────────
    if re.search(r'\b(it|that|this)\b', cmd) and any(
        w in cmd for w in ("open", "close", "launch", "play")
    ):
        try:
            from memory.context_manager import get_context
            resolved = get_context().resolve_pronoun("it")
            if resolved:
                cmd = re.sub(r'\b(it|that|this)\b', resolved, cmd)
        except Exception:
            pass

    # ── Multi-step autonomous tasks ───────────────────────────────────────────

    multi_step_patterns = [
        r"prepare (my|the) (.+?) (setup|session|mode)",
        r"start (my|the) (.+?) (session|routine|mode)",
        r"set up (.+?) (for|mode)",
        r"open (.+?) and (.+?) and (.+)",
        r"open (.+?) and (search|play|find) (.+)",
    ]
    for pattern in multi_step_patterns:
        if re.search(pattern, cmd):
            result = execute_task(cmd)
            if result:
                return result

    # ── Focus mode ────────────────────────────────────────────────────────────

    if re.search(r"(start|enable|activate)\s+(focus|study|work)\s*mode", cmd):
        duration = re.search(r"(\d+)\s*(minute|hour)s?", cmd)
        mins = int(duration.group(1)) * (60 if "hour" in duration.group(2) else 1) if duration else 25
        return start_focus(mins)

    if re.search(r"(stop|end|disable)\s+(focus|study|work)\s*mode", cmd):
        return stop_focus()

    if re.search(r"focus\s+status|how.*(focus|study)", cmd):
        return get_focus_status()

    # ── YouTube ───────────────────────────────────────────────────────────────

    if "youtube" in cmd:
        m = re.search(r"(?:search|play|find|open)\s+(.+?)\s*(?:on youtube|$)", cmd)
        if m:
            query  = m.group(1).strip()
            suffix = "latest stream" if re.search(r"\b(stream|live)\b", cmd) else ""
            threading.Thread(target=youtube_search, args=(f"{query} {suffix}".strip(),), daemon=True).start()
            return ""
        threading.Thread(target=open_youtube, daemon=True).start()
        return ""

    if re.search(r"\b(stream|live)\b", cmd):
        m = re.search(r"(?:open|play|show)\s+(.+?)\s+(?:stream|live)", cmd)
        if m:
            threading.Thread(target=youtube_search, args=(f"{m.group(1).strip()} latest stream",), daemon=True).start()
            return ""

    # ── Play/search ───────────────────────────────────────────────────────────

    play = re.search(r"(?:play|search)\s+(.+?)\s+on\s+(\w+)", cmd)
    if play:
        query, platform = play.group(1), play.group(2)
        if "spotify" in platform:
            threading.Thread(target=open_app, args=("spotify",), daemon=True).start()
            return ""
        threading.Thread(target=youtube_search, args=(query,), daemon=True).start()
        return ""

    # ── Web search ────────────────────────────────────────────────────────────

    web = re.search(r"(?:search|google|look up)\s+(?:for\s+)?(.+)", cmd)
    if web and not any(k in cmd for k in ("open", "file", "note", "timer")):
        threading.Thread(target=google_search, args=(web.group(1).strip(),), daemon=True).start()
        return ""

    # ── Open ──────────────────────────────────────────────────────────────────

    open_m = re.search(r"(?:open|launch|start|run)\s+(.+)", cmd)
    if open_m:
        target = open_m.group(1).strip()

        # URL
        if re.search(r'\.\w{2,4}$|^www\.', target):
            threading.Thread(target=open_url, args=(target,), daemon=True).start()
            return ""

        # File
        if "file" in cmd:
            filename = target.replace("file", "").strip()
            result   = open_file(filename)
            return "" if "opening" in result.lower() else result

        # App
        result = open_app(target)
        if result:
            try:
                from memory.context_manager import get_context
                get_context().register_entity(target, entity_type="app")
            except Exception:
                pass
            return ""

        # Fuzzy fallback
        if _depth == 0:
            resolved = _fuzzy_resolve(cmd)
            if resolved:
                print(f"Leon interpreted: '{cmd}' → '{resolved}'")
                return dispatch(resolved, _depth=1)

        return f"I couldn't find {target}, sir. Could you clarify?"

    # ── Close ─────────────────────────────────────────────────────────────────

    close_m = re.search(r"(?:close|kill|quit)\s+(.+)", cmd)
    if close_m:
        target = close_m.group(1).strip()
        result = close_app(target)
        if result:
            return ""
        if _depth == 0:
            resolved = _fuzzy_resolve(cmd)
            if resolved:
                return dispatch(resolved, _depth=1)
        return f"Couldn't close {target}, sir."

    # ── Files ─────────────────────────────────────────────────────────────────

    if any(k in cmd for k in ("find file", "look for file", "locate file", "search for file")):
        m = re.search(r"(?:find|look for|locate|search for)\s+(?:file\s+)?(.+)", cmd)
        if m:
            return find_file(m.group(1).strip())

    if re.search(r"(?:list|show)\s+files?\s+(?:in|from)?\s*(.+)", cmd):
        m = re.search(r"(?:list|show)\s+files?\s+(?:in|from)?\s*(.+)", cmd)
        if m:
            return list_files(m.group(1).strip())

    # ── System info ───────────────────────────────────────────────────────────

    if re.search(r"\b(cpu|processor)\b", cmd):
        return get_cpu()

    if re.search(r"\b(ram|memory)\b", cmd):
        return get_ram()

    if re.search(r"\b(battery|charge)\b", cmd):
        return get_battery()

    if re.search(r"\b(disk|storage|drive)\b", cmd):
        return get_disk()

    if re.search(r"\btime\b", cmd) and "timer" not in cmd and "set" not in cmd:
        return get_time()

    if re.search(r"\b(date|today)\b", cmd) and "weather" not in cmd and "set" not in cmd:
        return get_date()

    # ── Volume ────────────────────────────────────────────────────────────────

    if re.search(r"volume\s+up|increase\s+volume|turn\s+(?:it\s+)?up|louder", cmd):
        return set_volume_up()

    if re.search(r"volume\s+down|decrease\s+volume|turn\s+(?:it\s+)?down|quieter|lower", cmd):
        return set_volume_down()

    if re.search(r"\b(mute|silence|quiet)\b", cmd):
        return mute_volume()

    # ── Brightness ────────────────────────────────────────────────────────────

    if re.search(r"brightness\s+up|increase\s+brightness|brighter", cmd):
        return set_brightness_up()

    if re.search(r"brightness\s+down|decrease\s+brightness|dimmer", cmd):
        return set_brightness_down()

    # ── Screenshot ────────────────────────────────────────────────────────────

    if re.search(r"screenshot|screen\s+capture|capture\s+screen", cmd):
        return take_screenshot()

    # ── Timers & reminders ────────────────────────────────────────────────────

    timer = re.search(r"(?:set\s+)?(?:a\s+)?timer\s+(?:for\s+)?(\d+)\s*(second|minute|hour)s?", cmd)
    if timer:
        return set_timer(int(timer.group(1)), timer.group(2))

    remind = re.search(r"remind\s+me\s+(?:in\s+)?(\d+)\s*(second|minute|hour)s?\s+(?:to\s+)?(.+)", cmd)
    if remind:
        return set_reminder(int(remind.group(1)), remind.group(2), remind.group(3).strip())

    if re.search(r"(what|show|list).*(reminder|alarm|schedule)", cmd):
        return get_reminders()

    # ── Shutdown timer ────────────────────────────────────────────────────────

    shutdown_t = re.search(r"shutdown\s+(?:after|in)\s+(\d+)\s*(minute|hour)s?", cmd)
    if shutdown_t:
        return shutdown_after(int(shutdown_t.group(1)), shutdown_t.group(2))

    # ── Browser tab control ───────────────────────────────────────────────────

    if re.search(r"close\s+(all\s+)?(tabs?|browser|chrome|brave|firefox)", cmd):
        threading.Thread(target=close_browser_tab, daemon=True).start()
        return ""

    if re.search(r"pause\s+(the\s+)?(video|music|song)", cmd):
        threading.Thread(target=pause_video, daemon=True).start()
        return ""

    # ── Fuzzy last resort ─────────────────────────────────────────────────────

    if _depth == 0 and any(k in cmd for k in ("open", "close", "play", "launch", "start")):
        resolved = _fuzzy_resolve(cmd)
        if resolved:
            print(f"Leon interpreted: '{cmd}' → '{resolved}'")
            return dispatch(resolved, _depth=1)

    return None  # Pass to LLM
