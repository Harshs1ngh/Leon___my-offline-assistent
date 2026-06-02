# brain/engines/groq_engine.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
MODEL        = "llama-3.1-8b-instant"


def generate(prompt, *, system_prompt="", messages=None, max_tokens=60, temperature=0.7) -> str:
    if not GROQ_API_KEY:
        return "Groq API key not set, sir."
    msg_list = [{"role": "system", "content": system_prompt}]
    if messages:
        msg_list.extend(messages)
    msg_list.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": msg_list, "max_tokens": max_tokens, "temperature": temperature},
            timeout=15,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Groq error: {e}"
