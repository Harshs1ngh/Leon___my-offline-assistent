# voice/tts.py
import os
import queue
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

_BASE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ONNX_PATH   = os.path.join(_BASE, "kokoro-v1.0.int8.onnx")
_VOICES_PATH = os.path.join(_BASE, "voices-v1.0.bin")

_kokoro = None
try:
    from kokoro_onnx import Kokoro
    if os.path.isfile(_ONNX_PATH) and os.path.isfile(_VOICES_PATH):
        _kokoro = Kokoro(_ONNX_PATH, _VOICES_PATH)
        print("✅ TTS: edge-tts Andrew (primary) + Kokoro am_adam (fallback)")
    else:
        print("✅ TTS: edge-tts Andrew (primary)")
except Exception:
    print("✅ TTS: edge-tts Andrew (primary)")

_speaking     = False
_interrupt    = threading.Event()
_play_queue   = queue.Queue()
_synth_pool   = ThreadPoolExecutor(max_workers=2, thread_name_prefix="synth")
_current_proc = None
_proc_lock    = threading.Lock()


def _synth_edge(text: str) -> str | None:
    try:
        import asyncio, edge_tts
        async def _run():
            c = edge_tts.Communicate(text=text, voice="en-US-AndrewNeural", rate="+8%", pitch="-2Hz")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                path = f.name
            await c.save(path)
            return path
        return asyncio.run(_run())
    except Exception as e:
        print(f"edge-tts error: {e}")
        return _synth_kokoro(text)


def _synth_kokoro(text: str) -> str | None:
    if _kokoro is None:
        return None
    try:
        import soundfile as sf
        text    = text.replace("\n", " ").strip()
        s, sr   = _kokoro.create(text, voice="am_adam", speed=0.92, lang="en-us")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            path = f.name
        sf.write(path, s.astype(np.float32), sr)
        return path
    except Exception as e:
        print(f"Kokoro error: {e}")
        return None


def _synth(text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    return _synth_edge(text)


def _play_file(path: str):
    global _speaking, _current_proc
    if not path or not os.path.isfile(path):
        return
    _speaking = True
    try:
        proc = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with _proc_lock:
            _current_proc = proc
        while proc.poll() is None:
            if _interrupt.is_set():
                proc.terminate()
                break
            threading.Event().wait(0.02)
    except FileNotFoundError:
        print("❌ ffplay not found — install ffmpeg")
    except Exception as e:
        print(f"Playback error: {e}")
    finally:
        with _proc_lock:
            _current_proc = None
        _speaking = False
        try:
            os.remove(path)
        except Exception:
            pass


def _player_worker():
    global _speaking
    while True:
        try:
            future = _play_queue.get(timeout=0.3)
        except queue.Empty:
            _speaking = not _play_queue.empty()
            continue
        try:
            if _interrupt.is_set():
                try:
                    future.cancel()
                except Exception:
                    pass
                _play_queue.task_done()
                continue
            path = future.result(timeout=30)
            if path and not _interrupt.is_set():
                _play_file(path)
        except Exception as e:
            print(f"Player error: {e}")
        finally:
            try:
                _play_queue.task_done()
            except Exception:
                pass


threading.Thread(target=_player_worker, daemon=True, name="tts-player").start()


def say(text: str):
    global _speaking
    text = (text or "").strip()
    if not text:
        return
    _interrupt.clear()
    _play_queue.put(_synth_pool.submit(_synth, text))
    _speaking = True


def stop_speaking():
    global _speaking
    _interrupt.set()
    with _proc_lock:
        if _current_proc and _current_proc.poll() is None:
            try:
                _current_proc.terminate()
            except Exception:
                pass
    while not _play_queue.empty():
        try:
            f = _play_queue.get_nowait()
            try:
                f.cancel()
            except Exception:
                pass
            _play_queue.task_done()
        except queue.Empty:
            break
    _speaking = False
    threading.Timer(0.15, _interrupt.clear).start()


def is_speaking() -> bool:
    return _speaking or not _play_queue.empty()
