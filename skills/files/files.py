# skills/files/files.py
import os
import subprocess
import sys

SEARCH_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Pictures"),
    os.path.expanduser("~/Videos"),
    os.path.expanduser("~/Music"),
    os.path.expanduser("~"),
]

FOLDER_ALIASES = {
    "desktop":   os.path.expanduser("~/Desktop"),
    "downloads": os.path.expanduser("~/Downloads"),
    "documents": os.path.expanduser("~/Documents"),
    "pictures":  os.path.expanduser("~/Pictures"),
    "photos":    os.path.expanduser("~/Pictures"),
    "videos":    os.path.expanduser("~/Videos"),
    "music":     os.path.expanduser("~/Music"),
    "home":      os.path.expanduser("~"),
}


def find_file(filename: str) -> str:
    filename = filename.strip().lower()
    found = []
    for d in SEARCH_DIRS:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if not x.startswith(".")]
            for f in files:
                if filename in f.lower():
                    found.append(os.path.join(root, f))
            if len(found) >= 5:
                break
        if len(found) >= 5:
            break

    if not found:
        return f"No file matching '{filename}' found in your common folders, sir."
    if len(found) == 1:
        folder = os.path.basename(os.path.dirname(found[0]))
        return f"Found '{os.path.basename(found[0])}' in your {folder} folder, sir."
    names = [os.path.basename(p) for p in found[:3]]
    return f"Found {len(found)} matches, sir. First few: {', '.join(names)}."


def open_file(filename: str) -> str:
    filename = filename.strip().lower()
    for d in SEARCH_DIRS:
        if not os.path.exists(d):
            continue
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if not x.startswith(".")]
            for f in files:
                if filename in f.lower():
                    path = os.path.join(root, f)
                    try:
                        if sys.platform == "win32":
                            os.startfile(path)
                        elif sys.platform == "darwin":
                            subprocess.Popen(["open", path])
                        else:
                            subprocess.Popen(["xdg-open", path])
                        return f"Opening {os.path.basename(path)}, sir."
                    except Exception as e:
                        return f"Found it but couldn't open it, sir: {e}"
    return f"No file named '{filename}' found, sir."


def list_files(folder_name: str) -> str:
    path = FOLDER_ALIASES.get(folder_name.lower().strip(), os.path.expanduser(folder_name))
    if not os.path.exists(path):
        return f"Folder '{folder_name}' not found, sir."
    try:
        items = [f for f in os.listdir(path) if not f.startswith(".")]
        if not items:
            return f"The {folder_name} folder is empty, sir."
        files = [i for i in items if os.path.isfile(os.path.join(path, i))]
        dirs  = [i for i in items if os.path.isdir(os.path.join(path, i))]
        parts = []
        if dirs:
            parts.append(f"{len(dirs)} folders")
        if files:
            parts.append(f"{len(files)} files")
        return f"Your {folder_name} has {' and '.join(parts)}, sir."
    except PermissionError:
        return f"No permission to access {folder_name}, sir."
