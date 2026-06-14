# skills/browser/browser.py
import subprocess
import sys
import webbrowser
from urllib.parse import quote_plus


def _get_default_browser_cmd() -> list:
    if sys.platform == "win32":
        import winreg
        try:
            key  = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice")
            prog = winreg.QueryValueEx(key, "ProgId")[0]
            if "chrome" in prog.lower():
                return [r"C:\Program Files\Google\Chrome\Application\chrome.exe"]
            if "brave" in prog.lower():
                return [r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"]
            if "firefox" in prog.lower():
                return [r"C:\Program Files\Mozilla Firefox\firefox.exe"]
        except Exception:
            pass
    return []


def open_url(url: str):
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)


def google_search(query: str):
    webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")


def open_youtube():
    webbrowser.open("https://www.youtube.com")


def youtube_search(query: str):
    webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")


def close_browser_tab():
    import pyautogui
    pyautogui.hotkey("ctrl", "w")


def pause_video():
    import pyautogui
    pyautogui.press("space")


def open_in_browser(browser: str, url: str):
    browsers = {
        "brave":   r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "chrome":  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "edge":    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    }
    exe = browsers.get(browser.lower())
    if exe:
        try:
            subprocess.Popen([exe, url])
            return True
        except FileNotFoundError:
            pass
    webbrowser.open(url)
    return True
