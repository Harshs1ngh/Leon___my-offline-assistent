# utils/text_normalizer.py
import re


def normalize_for_tts(text: str) -> str:
    if not text:
        return text
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'_{1,2}(.*?)_{1,2}', r'\1', text)
    text = re.sub(r'₹\s*(\d[\d,]*)', r'\1 rupees', text)
    text = re.sub(r'\$\s*(\d[\d,]*)', r'\1 dollars', text)
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = re.sub(r'https?://', '', text)
    text = re.sub(r'\.com\b', ' dot com', text)
    text = re.sub(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', r'\1 \2 \3', text)
    text = re.sub(r'[&<>|^~\\]', ' ', text)
    text = re.sub(r'^\s*[-•*]\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()
