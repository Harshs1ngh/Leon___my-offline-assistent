# skills/system/desktop.py
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime

import psutil

# ── App name → executable mapping ────────────────────────────────────────────

_WIN_APPS = {
    "chrome":               r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "brave":                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "brave browser":        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "firefox":              r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "edge":                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "vs code":              "code",
    "vscode":               "code",
    "visual studio code":   "code",
    "notepad":              "notepad",
    "calculator":           "calc",
    "explorer":             "explorer",
    "file explorer":        "explorer",
    "spotify":              "spotify",
    "discord":              "discord",
    "telegram":             "telegram",
    "task manager":         "taskmgr",
    "control panel":        "control",
    "paint":                "mspaint",
    "vlc":                  "vlc",
    "terminal":             "cmd",
    "cmd":                  "cmd",
    "powershell":           "powershell",
    "whatsapp":             "whatsapp",
    "word":                 "winword",
    "excel":                "excel",
    "powerpoint":           "powerpnt",
    "obs":                  "obs64",
    "steam":                "steam",
}

_LINUX_APPS = {
    "chrome":       "google-chrome",
    "firefox":      "firefox",
    "vs code":      "code",
    "vscode":       "code",
    "spotify":      "spotify",
    "discord":      "discord",
    "vlc":          "vlc",
    "terminal":     "gnome-terminal",
    "calculator":   "gnome-calculator",
    "notepad":      "gedit",
    "files":        "nautilus",
}

_PROCESS_NAMES = {
    "chrome": "chrome", "google chrome": "chrome",
    "brave": "brave", "firefox": "firefox",
    "vs code": "Code", "vscode": "Code",
    "spotify": "Spotify", "discord": "Discord",
    "vlc": "vlc", "notepad": "notepad",
    "edge": "msedge", "telegram": "Telegram",
    "task manager": "Taskmgr",
}


def open_app(app_name: str) -> str | None:
    key = app_name.lower().strip()
    try:
        if sys.platform == "win32":
            exe = _WIN_APPS.get(key)
            if not exe:
                return None
            try:
                subprocess.Popen([exe])
            except FileNotFoundError:
                subprocess.Popen([exe], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            exe = _LINUX_APPS.get(key, key)
            subprocess.Popen([exe], start_new_session=True)
        return f"Opening {app_name}."
    except Exception as e:
        return None


def close_app(app_name: str) -> str | None:
    key  = app_name.lower().strip()
    proc = _PROCESS_NAMES.get(key, key)
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/f", "/im", f"{proc}.exe"], capture_output=True)
        else:
            subprocess.run(["pkill", "-f", proc], capture_output=True)
        return f"Closed {app_name}."
    except Exception:
        return None


def take_screenshot() -> str:
    try:
        from PIL import ImageGrab
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.expanduser(f"~/Desktop/leon_{ts}.png")
        ImageGrab.grab().save(path)
        return f"Screenshot saved to Desktop, sir."
    except ImportError:
        return "Install Pillow for screenshots: pip install Pillow"
    except Exception as e:
        return f"Screenshot failed: {e}"


def set_volume_up() -> str:
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import cast, POINTER
            subprocess.run(["powershell", "-c",
                "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"], capture_output=True)
        elif sys.platform == "linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "10%+"], capture_output=True)
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                "set volume output volume (output volume of (get volume settings) + 10)"], capture_output=True)
        return "Volume up, sir."
    except Exception:
        return "Couldn't adjust volume, sir."


def set_volume_down() -> str:
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-c",
                "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"], capture_output=True)
        elif sys.platform == "linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "10%-"], capture_output=True)
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e",
                "set volume output volume (output volume of (get volume settings) - 10)"], capture_output=True)
        return "Volume down, sir."
    except Exception:
        return "Couldn't adjust volume, sir."


def mute_volume() -> str:
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-c",
                "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"], capture_output=True)
        elif sys.platform == "linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "toggle"], capture_output=True)
        elif sys.platform == "darwin":
            subprocess.run(["osascript", "-e", "set volume with output muted"], capture_output=True)
        return "Muted, sir."
    except Exception:
        return "Couldn't mute, sir."


def set_brightness_up() -> str:
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-c",
                "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [math]::Min(100, (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness + 10))"],
                capture_output=True)
        elif sys.platform == "linux":
            subprocess.run(["brightnessctl", "set", "+10%"], capture_output=True)
        return "Brightness increased, sir."
    except Exception:
        return "Couldn't adjust brightness, sir."


def set_brightness_down() -> str:
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-c",
                "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [math]::Max(0, (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness - 10))"],
                capture_output=True)
        elif sys.platform == "linux":
            subprocess.run(["brightnessctl", "set", "10%-"], capture_output=True)
        return "Brightness decreased, sir."
    except Exception:
        return "Couldn't adjust brightness, sir."


def get_cpu() -> str:
    try:
        usage = psutil.cpu_percent(interval=0.5)
        cores = psutil.cpu_count()
        return f"CPU is at {usage:.0f} percent across {cores} cores, sir."
    except Exception:
        return "Couldn't read CPU stats, sir."


def get_ram() -> str:
    try:
        m    = psutil.virtual_memory()
        used = m.used / (1024**3)
        total = m.total / (1024**3)
        return f"RAM is at {m.percent:.0f} percent — {used:.1f} of {total:.1f} gigabytes used, sir."
    except Exception:
        return "Couldn't read RAM stats, sir."


def get_battery() -> str:
    try:
        b = psutil.sensors_battery()
        if b is None:
            return "No battery detected, sir."
        status = "plugged in" if b.power_plugged else "on battery"
        return f"Battery is at {b.percent:.0f} percent and {status}, sir."
    except Exception:
        return "Couldn't read battery, sir."


def get_disk() -> str:
    try:
        d     = psutil.disk_usage("/")
        free  = d.free / (1024**3)
        total = d.total / (1024**3)
        return f"Disk is {d.percent:.0f} percent full — {free:.1f} gigabytes free of {total:.1f} total, sir."
    except Exception:
        return "Couldn't read disk stats, sir."


def get_time() -> str:
    now    = datetime.now()
    hour   = now.hour % 12 or 12
    minute = now.strftime("%M")
    ampm   = "AM" if now.hour < 12 else "PM"
    return f"It's {hour} {minute} {ampm}, sir."


def get_date() -> str:
    return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}, sir."


def shutdown_after(amount: int, unit: str) -> str:
    seconds = amount * (3600 if "hour" in unit else 60)
    def _do():
        time.sleep(seconds)
        if sys.platform == "win32":
            subprocess.run(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.run(["shutdown", "-h", "now"])
    threading.Thread(target=_do, daemon=True).start()
    return f"System will shut down in {amount} {unit}{'s' if amount > 1 else ''}, sir."
