import time
import requests
import re
import urllib.parse
from typing import List, Dict, Any, Callable, Optional

# Delimiter used to batch multiple paragraphs into a single API request
BATCH_DELIMITER = "\n\n⟦§⟧\n\n"
SPLIT_REGEX = re.compile(r"\s*⟦§⟧\s*")

def translate_gtx(text: str, source_lang: str = "auto", target_lang: str = "vi", retries: int = 3, timeout: int = 15) -> str:
    """
    Translates text using Google's public translation endpoint with automatic retries.
    """
    if not text or not text.strip():
        return text

    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source_lang,
        "tl": target_lang,
        "dt": "t"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.post(
                url, 
                params=params, 
                data={"q": text}, 
                headers=headers,
                timeout=timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0 and data[0]:
                    parts = [segment[0] for segment in data[0] if segment and segment[0]]
                    return "".join(parts)
            elif resp.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
            else:
                last_error = f"Status {resp.status_code}: {resp.text[:100]}"
                time.sleep(1.0 * (attempt + 1))
        except Exception as e:
            last_error = str(e)
            time.sleep(1.0 * (attempt + 1))

    # If GTX fails, attempt fallback via get
    try:
        get_params = {**params, "q": text[:1500]}
        resp = requests.get(url, params=get_params, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0 and data[0]:
                return "".join([s[0] for s in data[0] if s and s[0]])
    except Exception:
        pass

    # If completely failed, return original text to avoid crash
    print(f"[Translator Warning] Failed translating chunk: {last_error}")
    return text


def translate_gemini(text: str, api_key: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
    """
    Translates text using Google Gemini Flash API for high-grade literary translation.
    """
    if not text or not text.strip():
        return text
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = (
        f"You are a professional literary and document translator. "
        f"Translate the following text into natural, fluent, and accurate {target_lang} (Vietnamese). "
        f"Preserve formatting, tone, and line breaks. Do not add conversational remarks or explanations. "
        f"Only return the translation:\n\n{text}"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        else:
            print(f"[Gemini Error] {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[Gemini Exception] {e}")
        
    # Fallback to Google GTX if Gemini fails
    return translate_gtx(text, source_lang, target_lang)


class DocumentTranslator:
    def __init__(self, api_key: Optional[str] = None, engine: str = "google"):
        self.api_key = api_key
        self.engine = engine  # 'google' or 'gemini'

    def translate_single(self, text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
        if self.engine == "gemini" and self.api_key:
            return translate_gemini(text, self.api_key, source_lang, target_lang)
        return translate_gtx(text, source_lang, target_lang)

    def translate_batch(
        self,
        paragraphs: List[str],
        source_lang: str = "auto",
        target_lang: str = "vi",
        max_batch_chars: int = 1800,
        pause_between_batches: float = 0.2,
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        should_stop_check: Optional[Callable[[], bool]] = None
    ) -> List[str]:
        """
        Translates a list of paragraphs in batches for optimal speed and reliability.
        Updates progress_callback on each batch.
        """
        total = len(paragraphs)
        if total == 0:
            return []

        results = [""] * total
        current_batch_indices = []
        current_batch_len = 0

        # Helper to process a batch
        def process_batch(indices: List[int]):
            if not indices:
                return

            # Check if user requested cancel/stop
            if should_stop_check and should_stop_check():
                return

            batch_texts = [paragraphs[i] for i in indices]
            # If all are empty or whitespace
            if all(not t.strip() for t in batch_texts):
                for i in indices:
                    results[i] = paragraphs[i]
                return

            joined_text = BATCH_DELIMITER.join(batch_texts)
            translated_joined = self.translate_single(joined_text, source_lang, target_lang)
            split_translated = SPLIT_REGEX.split(translated_joined)

            if len(split_translated) == len(indices):
                for idx, t_text in zip(indices, split_translated):
                    results[idx] = t_text.strip()
            else:
                # If delimiter was lost or modified, translate one by one
                for i in indices:
                    p_orig = paragraphs[i]
                    if not p_orig.strip():
                        results[i] = p_orig
                    else:
                        results[i] = self.translate_single(p_orig, source_lang, target_lang)
                        time.sleep(0.05)

            if progress_callback:
                done_count = sum(1 for r in results if r != "")
                latest_sample = {
                    "index": indices[-1],
                    "original": paragraphs[indices[-1]][:120],
                    "translated": results[indices[-1]][:120]
                }
                progress_callback(done_count, total, latest_sample)

            time.sleep(pause_between_batches)

        for i, text in enumerate(paragraphs):
            t_len = len(text)
            # If a single paragraph is larger than max_batch_chars, process previous and then process this
            if t_len > max_batch_chars:
                if current_batch_indices:
                    process_batch(current_batch_indices)
                    current_batch_indices = []
                    current_batch_len = 0
                process_batch([i])
                continue

            if current_batch_len + t_len > max_batch_chars:
                process_batch(current_batch_indices)
                current_batch_indices = [i]
                current_batch_len = t_len
            else:
                current_batch_indices.append(i)
                current_batch_len += t_len + len(BATCH_DELIMITER)

        if current_batch_indices:
            process_batch(current_batch_indices)

        return results
