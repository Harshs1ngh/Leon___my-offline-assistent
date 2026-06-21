# skills/schedule/scheduler.py
import threading
import time
from datetime import datetime

_reminders: list[dict] = []


def _unit_seconds(amount: int, unit: str) -> int:
    u = unit.lower().rstrip("s")
    if u == "second":
        return amount
    elif u == "minute":
        return amount * 60
    elif u == "hour":
        return amount * 3600
    return amount


def set_timer(amount: int, unit: str) -> str:
    seconds = _unit_seconds(amount, unit)

    def _ring():
        time.sleep(seconds)
        from voice.tts import say
        say(f"Timer done, sir. Your {amount} {unit} timer is up.")

    threading.Thread(target=_ring, daemon=True).start()
    return f"Timer set for {amount} {unit}{'s' if amount > 1 else ''}, sir."


def set_reminder(amount: int, unit: str, task: str) -> str:
    seconds = _unit_seconds(amount, unit)
    remind_at = datetime.now().timestamp() + seconds

    _reminders.append({"task": task, "at": remind_at, "done": False})

    def _remind():
        time.sleep(seconds)
        from voice.tts import say
        say(f"Reminder, sir: {task}")

    threading.Thread(target=_remind, daemon=True).start()
    return f"I'll remind you to {task} in {amount} {unit}{'s' if amount > 1 else ''}, sir."


def get_reminders() -> str:
    active = [r for r in _reminders if not r["done"]
              and r["at"] > datetime.now().timestamp()]
    if not active:
        return "No upcoming reminders, sir."
    items = [r["task"] for r in active[:3]]
    return f"Upcoming reminders: {', '.join(items)}, sir."
