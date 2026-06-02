# brain/engines/ollama_engine.py
import json
import requests

OLLAMA_URL      = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
MODEL           = "gemma2:2b"
_HEADERS        = {"Content-Type": "application/json"}


def is_available() -> bool:
    try:
        resp       = requests.get(OLLAMA_TAGS_URL, timeout=3)
        models     = [m["name"] for m in resp.json().get("models", [])]
        model_base = MODEL.split(":")[0].lower()
        if not any(model_base in m.lower() for m in models):
            print(f"⚠️  Model '{MODEL}' not found. Run: ollama pull {MODEL}")
            return False
        print(f"🔥 Warming {MODEL}...")
        requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False, "options": {"num_predict": 1},
        }, timeout=60)
        print(f"✅ Brain: Ollama ({MODEL}) — offline")
        return True
    except Exception:
        return False


def generate_stream(prompt, *, system_prompt="", messages=None, max_tokens=60, temperature=0.7):
    msg_list = []
    if system_prompt:
        msg_list.append({"role": "system", "content": system_prompt})
    if messages:
        msg_list.extend(messages)
    msg_list.append({"role": "user", "content": prompt})

    payload = {
        "model": MODEL, "messages": msg_list, "stream": True,
        "options": {"temperature": temperature, "num_predict": max_tokens, "top_p": 0.9},
    }
    try:
        with requests.post(OLLAMA_URL, json=payload, headers=_HEADERS, stream=True, timeout=60) as resp:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break
    except requests.Timeout:
        yield "Sorry, that took too long, sir."
    except Exception as e:
        yield f"Ollama error: {e}"


def generate(prompt, *, system_prompt="", messages=None, max_tokens=200, temperature=0.7) -> str:
    return "".join(generate_stream(
        prompt, system_prompt=system_prompt, messages=messages,
        max_tokens=max_tokens, temperature=temperature,
    ))
