# skills/focus/focus.py
import threading
import time

_focus_active    = False
_focus_end_time  = 0.0
_focus_minutes   = 0
_focus_timer     = None
_distraction_apps = [
    "instagram", "youtube shorts", "tiktok", "twitter", "reddit",
    "facebook", "snapchat", "netflix", "prime video",
]


def start_focus(minutes: int = 25) -> str:
    global _focus_active, _focus_end_time, _focus_minutes, _focus_timer

    _focus_active   = True
    _focus_minutes  = minutes
    _focus_end_time = time.monotonic() + minutes * 60

    def _end():
        global _focus_active
        time.sleep(minutes * 60)
        if _focus_active:
            _focus_active = False
            from voice.tts import say
            say(f"Focus session complete, sir. {minutes} minutes done.")

    _focus_timer = threading.Thread(target=_end, daemon=True)
    _focus_timer.start()

    # Start monitoring thread
    threading.Thread(target=_monitor, daemon=True).start()

    return f"Focus mode on, sir. {minutes} minutes. Distractions will be flagged."


def stop_focus() -> str:
    global _focus_active
    _focus_active = False
    return "Focus mode off, sir. Good work."


def get_focus_status() -> str:
    if not _focus_active:
        return "No active focus session, sir."
    remaining = max(0, int((_focus_end_time - time.monotonic()) / 60))
    return f"Focus mode active, sir. {remaining} minutes remaining."


def is_focus_active() -> bool:
    return _focus_active


def _monitor():
    """Check every 30s for distraction apps while in focus mode."""
    import psutil
    warned = set()
    while _focus_active:
        time.sleep(30)
        if not _focus_active:
            break
        try:
            running = [p.name().lower() for p in psutil.process_iter(["name"])]
            for app in _distraction_apps:
                if any(app in r for r in running) and app not in warned:
                    warned.add(app)
                    from voice.tts import say
                    say(f"Sir, {app} is open. You're in focus mode.")
        except Exception:
            pass
