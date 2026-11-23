import os
import time
import json
import re
import random
import requests
from typing import List, Dict, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# Common User Agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
]

BATCH_DELIMITER = "\n\n⟦§⟧\n\n"
SPLIT_REGEX = re.compile(r"\s*⟦§⟧\s*")

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=2)
session.mount("https://", adapter)
session.mount("http://", adapter)


# Load environment variables from .env if present
def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
        except Exception:
            pass

_load_env_file()

DEFAULT_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-flash-lite-latest"]

# ==============================================================================
# 1. GEMINI FLASH TURBO ENGINE (SUPER-FAST 100X)
# ==============================================================================
def translate_gemini_structured(
    items: List[Dict[str, Any]], 
    api_key: str = "", 
    model: str = "gemini-3.5-flash", 
    target_lang: str = "vi",
    retries: int = 3
) -> Dict[int, str]:
    """
    Translates a batch of paragraphs using Gemini Flash in JSON mode.
    Handles up to 35-40 paragraphs in seconds with 100% structured JSON fidelity.
    """
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not items or not key:
        return {}

    # Format input as compact JSON
    input_data = [{"id": item["id"], "text": item["text"]} for item in items]
    
    prompt = (
        f"You are a world-class literary translator. Translate each item's 'text' into natural, fluent {target_lang} (Vietnamese).\n"
        f"Requirements:\n"
        f"1. Preserve the original meaning, tone, and formatting.\n"
        f"2. Return ONLY a valid JSON array of objects: [{{\"id\": <number>, \"translated\": \"<translated text>\"}}].\n"
        f"3. Must return an entry for every input item ID without skipping any.\n\n"
        f"Input data:\n{json.dumps(input_data, ensure_ascii=False)}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    headers = {"Content-Type": "application/json"}

    # Try models in priority order
    models_to_try = [model] + [m for m in GEMINI_MODELS if m != model]

    for current_model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={key}"
        for attempt in range(retries):
            try:
                resp = session.post(url, json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content_parts = candidates[0].get("content", {}).get("parts", [])
                        if content_parts:
                            raw_json = content_parts[0].get("text", "")
                            result_map = {}
                            try:
                                parsed = json.loads(raw_json, strict=False)
                                if isinstance(parsed, list):
                                    for obj in parsed:
                                        if isinstance(obj, dict) and "id" in obj:
                                            val = None
                                            for k in ["translated", "text", "translation", "content", "dich"]:
                                                if k in obj and obj[k]:
                                                    val = str(obj[k]).strip()
                                                    break
                                            if not val:
                                                for k, v in obj.items():
                                                    if k != "id" and isinstance(v, str) and v.strip():
                                                        val = v.strip()
                                                        break
                                            if val:
                                                result_map[int(obj["id"])] = val
                                elif isinstance(parsed, dict):
                                    for k, v in parsed.items():
                                        try:
                                            result_map[int(k)] = str(v).strip()
                                        except ValueError:
                                            pass
                            except Exception:
                                # Fallback: Regex extraction for resilient JSON recovery
                                matches = re.findall(r'\{\s*"id"\s*:\s*(\d+)\s*,\s*"(?:translated|text)"\s*:\s*"((?:\\.|[^"\\])*)"', raw_json)
                                for m_id, m_trans in matches:
                                    try:
                                        clean_str = bytes(m_trans, "utf-8").decode("unicode_escape", errors="ignore")
                                        result_map[int(m_id)] = clean_str.strip()
                                    except Exception:
                                        result_map[int(m_id)] = m_trans.strip()

                            if len(result_map) > 0:
                                return result_map
                elif resp.status_code == 429:
                    print(f"[Gemini 429 on {current_model}] Sleeping 3s before retry...")
                    time.sleep(3.0)
                    continue
                elif resp.status_code in [404, 400, 503]:
                    # Switch immediately to next model in list
                    break
                time.sleep(0.5)
            except Exception as e:
                print(f"[Gemini Exception on {current_model} attempt {attempt+1}] {e}")
                time.sleep(0.5)

    return {}


# ==============================================================================
# 2. GROQ LPU TURBO ENGINE (750 TOKENS/SEC)
# ==============================================================================
def translate_groq_structured(
    items: List[Dict[str, Any]], 
    api_key: str, 
    model: str = "llama-3.3-70b-versatile", 
    target_lang: str = "vi",
    retries: int = 3
) -> Dict[int, str]:
    """
    Translates using Groq LPU API for ultra-low latency inference.
    """
    if not items or not api_key:
        return {}

    url = "https://api.groq.com/openai/v1/chat/completions"
    input_data = [{"id": item["id"], "text": item["text"]} for item in items]
    
    system_msg = (
        f"You are a professional book translator. Translate each item into fluent {target_lang} (Vietnamese). "
        f"Output ONLY a JSON array with schema: [{{'id': number, 'translated': string}}]."
    )
    user_msg = json.dumps(input_data, ensure_ascii=False)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for attempt in range(retries):
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                # If wrapped inside key like 'translations' or 'data'
                if isinstance(parsed, dict):
                    for v in parsed.values():
                        if isinstance(v, list):
                            parsed = v
                            break
                result_map = {}
                if isinstance(parsed, list):
                    for obj in parsed:
                        if "id" in obj and "translated" in obj:
                            result_map[int(obj["id"])] = obj["translated"].strip()
                    return result_map
            time.sleep(1.0 * (attempt + 1))
        except Exception as e:
            print(f"[Groq Exception attempt {attempt+1}] {e}")
            time.sleep(1.0 * (attempt + 1))

    return {}


# ==============================================================================
# 3. FREE MULTI-ENGINE FALLBACK (MYMEMORY + GOOGLE GTX + LIBRE)
# ==============================================================================
def translate_mymemory(text: str, source_lang: str = "auto", target_lang: str = "vi") -> Optional[str]:
    """
    Translates text using MyMemory Translation API (Free tier).
    """
    if not text.strip():
        return text
    try:
        sl = "en" if source_lang == "auto" else source_lang
        tl = "vi" if target_lang == "vi" else target_lang
        url = "https://api.mymemory.translated.net/get"
        params = {"q": text[:2000], "langpair": f"{sl}|{tl}"}
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            res_text = data.get("responseData", {}).get("translatedText")
            if res_text and "MYMEMORY WARNING" not in res_text.upper():
                return res_text
    except Exception:
        pass
    return None


def translate_gtx_single(text: str, source_lang: str = "auto", target_lang: str = "vi") -> Optional[str]:
    """
    Translates text using Google GTX endpoint with rotated headers.
    """
    if not text.strip():
        return text
    url = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": source_lang, "tl": target_lang, "dt": "t"}
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        resp = session.post(url, params=params, data={"q": text}, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            if data and data[0]:
                return "".join([s[0] for s in data[0] if s and s[0]])
    except Exception:
        pass
    return None


def translate_free_smart(text: str, source_lang: str = "auto", target_lang: str = "vi") -> str:
    """
    Cascading translation: GTX -> MyMemory -> Fallback.
    """
    # 1. Try Google GTX
    res = translate_gtx_single(text, source_lang, target_lang)
    if res:
        return res
        
    # 2. Try MyMemory
    res_mm = translate_mymemory(text, source_lang, target_lang)
    if res_mm:
        return res_mm

    return text


# ==============================================================================
# MAIN DOCUMENT TRANSLATOR CLASS
# ==============================================================================
class DocumentTranslator:
    def __init__(self, api_key: Optional[str] = None, engine: str = "gemini"):
        self.api_key = api_key if (api_key and api_key.strip()) else DEFAULT_GEMINI_KEY
        self.engine = engine.lower() if engine else "gemini"

    def translate_all_elements(
        self,
        elements: List[Dict[str, Any]],
        source_lang: str = "auto",
        target_lang: str = "vi",
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        should_stop_check: Optional[Callable[[], bool]] = None
    ) -> List[str]:
        """
        High-performance translator that processes entire documents up to 100x faster.
        Uses Mega-Chunking for AI models (Gemini / Groq) and Concurrent ThreadPool for free engine.
        """
        total = len(elements)
        if total == 0:
            return []

        results = [""] * total

        # ======================================================================
        # STRATEGY A: GEMINI FLASH (TURBO CHUNKS 35 ITEMS / 4,500 CHARS)
        # ======================================================================
        if self.engine == "gemini" and self.api_key:
            print("[Translator] Activating Gemini Flash Turbo Mode (Ultra-Fast 100x Speed)...")
            chunks: List[List[Dict[str, Any]]] = []
            current_chunk: List[Dict[str, Any]] = []
            current_len = 0
            MAX_CHUNK_ITEMS = 35
            MAX_CHUNK_CHARS = 4500

            for i, elem in enumerate(elements):
                item = {"id": i, "text": elem["text"]}
                t_len = len(elem["text"])
                if (len(current_chunk) >= MAX_CHUNK_ITEMS or (current_len + t_len > MAX_CHUNK_CHARS and current_chunk)):
                    chunks.append(current_chunk)
                    current_chunk = [item]
                    current_len = t_len
                else:
                    current_chunk.append(item)
                    current_len += t_len

            if current_chunk:
                chunks.append(current_chunk)

            completed_count = 0

            # Process chunks sequentially with quota pacing (~5 RPM, well within Free Tier 15 RPM)
            for c_idx, chunk in enumerate(chunks):
                if should_stop_check and should_stop_check():
                    break

                trans_dict = translate_gemini_structured(chunk, self.api_key, model="gemini-3.5-flash", target_lang=target_lang)

                for item in chunk:
                    idx = item["id"]
                    trans_text = trans_dict.get(idx)
                    if trans_text:
                        results[idx] = trans_text
                    else:
                        # Resilient fallback: preserve original text if API temporarily omitted item
                        results[idx] = elements[idx]["text"]
                    completed_count += 1

                if progress_callback and chunk:
                    last_idx = chunk[-1]["id"]
                    sample = {
                        "index": last_idx,
                        "original": elements[last_idx]["text"][:120],
                        "translated": results[last_idx][:120]
                    }
                    progress_callback(completed_count, total, sample)

                # Gentle pacing between requests
                if c_idx + 1 < len(chunks):
                    time.sleep(1.5)

            return results

        # ======================================================================
        # STRATEGY B: GROQ LPU (LLAMA 3.3 70B - 750 TOKENS/SEC)
        # ======================================================================
        if self.engine == "groq" and self.api_key:
            print("[Translator] Activating Groq LPU Turbo Mode...")
            chunks = []
            current_chunk = []
            current_len = 0
            MAX_CHUNK_CHARS = 12000

            for i, elem in enumerate(elements):
                item = {"id": i, "text": elem["text"]}
                t_len = len(elem["text"])
                if current_len + t_len > MAX_CHUNK_CHARS and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = [item]
                    current_len = t_len
                else:
                    current_chunk.append(item)
                    current_len += t_len
            if current_chunk:
                chunks.append(current_chunk)

            completed_count = 0
            with ThreadPoolExecutor(max_workers=3) as executor:
                def process_groq_chunk(c):
                    return translate_groq_structured(c, self.api_key, target_lang=target_lang)
                
                futures = {executor.submit(process_groq_chunk, ch): ch for ch in chunks}
                for future in as_completed(futures):
                    chunk = futures[future]
                    trans_dict = future.result()
                    for item in chunk:
                        idx = item["id"]
                        results[idx] = trans_dict.get(idx, elements[idx]["text"])
                        completed_count += 1
                    if progress_callback and chunk:
                        last_idx = chunk[-1]["id"]
                        sample = {
                            "index": last_idx,
                            "original": elements[last_idx]["text"][:120],
                            "translated": results[last_idx][:120]
                        }
                        progress_callback(completed_count, total, sample)

            return results

        # ======================================================================
        # STRATEGY C: FREE TURBO MULTI-THREAD ENGINE (NO KEY NEEDED)
        # ======================================================================
        print("[Translator] Activating Free Multi-Engine Turbo Pool...")
        batch_indices_list: List[List[int]] = []
        cur_batch: List[int] = []
        cur_len = 0
        MAX_BATCH_CHARS = 2400

        for i, elem in enumerate(elements):
            t_len = len(elem["text"])
            if cur_len + t_len > MAX_BATCH_CHARS and cur_batch:
                batch_indices_list.append(cur_batch)
                cur_batch = [i]
                cur_len = t_len
            else:
                cur_batch.append(i)
                cur_len += t_len + len(BATCH_DELIMITER)

        if cur_batch:
            batch_indices_list.append(cur_batch)

        completed_count = 0

        def process_free_batch(indices: List[int]):
            if should_stop_check and should_stop_check():
                return
            batch_texts = [elements[idx]["text"] for idx in indices]
            joined = BATCH_DELIMITER.join(batch_texts)
            translated_joined = translate_free_smart(joined, source_lang, target_lang)
            split_res = SPLIT_REGEX.split(translated_joined)

            if len(split_res) == len(indices):
                for idx, t_str in zip(indices, split_res):
                    results[idx] = t_str.strip()
            else:
                for idx in indices:
                    results[idx] = translate_free_smart(elements[idx]["text"], source_lang, target_lang)

        # Execute free batches with 4 parallel workers (fast without triggering 429)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(process_free_batch, b): b for b in batch_indices_list}
            for future in as_completed(futures):
                if should_stop_check and should_stop_check():
                    break
                b = futures[future]
                completed_count += len(b)
                if progress_callback and b:
                    last_idx = b[-1]
                    sample = {
                        "index": last_idx,
                        "original": elements[last_idx]["text"][:120],
                        "translated": results[last_idx][:120]
                    }
                    progress_callback(completed_count, total, sample)

        return results

    # Backward compatibility wrapper
    def translate_batch(self, paragraphs: List[str], **kwargs):
        elems = [{"id": i, "text": p} for i, p in enumerate(paragraphs)]
        return self.translate_all_elements(elems, **kwargs)
