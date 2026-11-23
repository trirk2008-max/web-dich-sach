import os
import time
import json
import uuid
import threading
import asyncio
import requests
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from translator import DocumentTranslator
from document_handler import extract_document, export_docx, export_pdf, export_txt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
TASKS_DIR = os.path.join(BASE_DIR, "tasks")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TASKS_DIR, exist_ok=True)

# Load .env file
def _load_env_file():
    env_path = os.path.join(BASE_DIR, ".env")
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

app = FastAPI(title="Dịch Sách & Tài Liệu Dài", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory tasks store
TASKS: Dict[str, Dict[str, Any]] = {}

def save_task_to_disk(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return
    path = os.path.join(TASKS_DIR, f"{task_id}.json")
    try:
        # Save a clean copy
        serializable = {k: v for k, v in task.items() if k not in ["_stop_flag", "_elements"]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Save Task Error] {e}")

def load_tasks_from_disk():
    if not os.path.exists(TASKS_DIR):
        return
    for fname in os.listdir(TASKS_DIR):
        if fname.endswith(".json"):
            task_id = fname[:-5]
            fpath = os.path.join(TASKS_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    TASKS[task_id] = data
            except Exception:
                pass

# Load existing tasks on startup
load_tasks_from_disk()


def run_translation_worker(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return

    try:
        elements = task.get("_elements", [])
        if not elements:
            # Extract document in background without blocking upload
            task["status"] = "preparing"
            save_task_to_disk(task_id)
            doc_data = extract_document(task["original_path"])
            elements = doc_data["elements"]
            task["_elements"] = elements
            task["total_words"] = doc_data["total_words"]
            task["total_paragraphs"] = doc_data["total_paragraphs"]
            task["estimated_pages"] = doc_data["estimated_pages"]
            task["status"] = "processing"
            save_task_to_disk(task_id)

        engine = task.get("engine", "google")
        api_key = task.get("api_key")
        source_lang = task.get("source_lang", "auto")
        target_lang = task.get("target_lang", "vi")

        translator = DocumentTranslator(api_key=api_key, engine=engine)
        paragraphs_text = [elem["text"] for elem in elements]
        total_count = len(paragraphs_text)

        words_per_elem = [elem.get("words", 1) for elem in elements]
        total_words = sum(words_per_elem)
        task["total_words"] = total_words
        task["total_paragraphs"] = total_count

        start_time = time.time()
        task["start_time"] = start_time

        def progress_callback(done_count: int, total: int, latest_sample: Dict[str, Any]):
            now = time.time()
            elapsed = max(0.1, now - start_time)
            completed_words = sum(words_per_elem[:done_count])
            speed_wpm = int((completed_words / elapsed) * 60)
            
            percent = round((done_count / total) * 100, 1)
            remaining_words = total_words - completed_words
            eta_seconds = int((remaining_words / max(1, speed_wpm)) * 60) if speed_wpm > 0 else 0

            task["completed_paragraphs"] = done_count
            task["completed_words"] = completed_words
            task["progress_percent"] = percent
            task["speed_wpm"] = speed_wpm
            task["elapsed_seconds"] = int(elapsed)
            task["eta_seconds"] = eta_seconds

            recent_logs = task.setdefault("recent_logs", [])
            recent_logs.append({
                "time": time.strftime("%H:%M:%S"),
                "original": latest_sample.get("original", ""),
                "translated": latest_sample.get("translated", "")
            })
            if len(recent_logs) > 50:
                task["recent_logs"] = recent_logs[-50:]

            # Save state periodically
            save_task_to_disk(task_id)

        def stop_check() -> bool:
            return task.get("_stop_flag", False)

        # Execute high-speed translation
        translated_results = translator.translate_all_elements(
            elements=elements,
            source_lang=source_lang,
            target_lang=target_lang,
            progress_callback=progress_callback,
            should_stop_check=stop_check
        )

        if task.get("_stop_flag"):
            task["status"] = "stopped"
            save_task_to_disk(task_id)
            return

        # Map results back to element IDs
        trans_map = {}
        for elem, trans_text in zip(elements, translated_results):
            trans_map[elem["id"]] = trans_text
            # Store translated text in elements for easy viewer access
            elem["translated_text"] = trans_text

        task["translated_map"] = {str(k): v for k, v in trans_map.items()}

        # Generate exported files
        clean_base_name = os.path.splitext(task["filename"])[0]
        safe_name = "".join(c for c in clean_base_name if c.isalnum() or c in (' ', '_', '-')).strip()
        if not safe_name:
            safe_name = "TaiLieu"

        docx_path = os.path.join(OUTPUT_DIR, f"{task_id}_{safe_name}_Dich_VI.docx")
        bilingual_path = os.path.join(OUTPUT_DIR, f"{task_id}_{safe_name}_SongNgu_VI.docx")
        pdf_path = os.path.join(OUTPUT_DIR, f"{task_id}_{safe_name}_Dich_VI.pdf")
        txt_path = os.path.join(OUTPUT_DIR, f"{task_id}_{safe_name}_Dich_VI.txt")

        # 1. DOCX Standard
        try:
            export_docx(task["original_path"], elements, trans_map, docx_path, bilingual=False)
            task["output_files"]["docx"] = os.path.basename(docx_path)
        except Exception as e:
            print(f"[Export DOCX error] {e}")

        # 2. DOCX Bilingual
        try:
            export_docx(task["original_path"], elements, trans_map, bilingual_path, bilingual=True)
            task["output_files"]["docx_bilingual"] = os.path.basename(bilingual_path)
        except Exception as e:
            print(f"[Export Bilingual DOCX error] {e}")

        # 3. PDF
        try:
            export_pdf(elements, trans_map, pdf_path, title=f"Bản Dịch: {task['filename']}")
            task["output_files"]["pdf"] = os.path.basename(pdf_path)
        except Exception as e:
            print(f"[Export PDF error] {e}")

        # 4. TXT
        try:
            export_txt(elements, trans_map, txt_path, bilingual=False)
            task["output_files"]["txt"] = os.path.basename(txt_path)
        except Exception as e:
            print(f"[Export TXT error] {e}")

        task["status"] = "completed"
        task["progress_percent"] = 100.0
        task["completed_paragraphs"] = total_count
        task["completed_words"] = total_words
        task["elapsed_seconds"] = int(time.time() - start_time)
        task["eta_seconds"] = 0
        save_task_to_disk(task_id)

    except Exception as e:
        task["status"] = "error"
        task["error_message"] = str(e)
        save_task_to_disk(task_id)
        print(f"[Translation Worker Failure] {e}")


@app.get("/", response_class=HTMLResponse)
def index_page():
    html_file = os.path.join(TEMPLATES_DIR, "index.html")
    with open(html_file, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/config")
def get_config():
    has_key = bool(os.environ.get("GEMINI_API_KEY"))
    return {
        "has_server_gemini_key": has_key,
        "default_engine": "gemini" if has_key else "free"
    }


@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_lang: str = Form("vi"),
    source_lang: str = Form("auto"),
    engine: str = Form("gemini"),
    api_key: Optional[str] = Form(None),
    bilingual: bool = Form(False)
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.docx', '.pdf', '.txt', '.md']:
        raise HTTPException(
            status_code=400, 
            detail="Định dạng tệp không được hỗ trợ! Vui lòng tải file Word (.docx), PDF (.pdf) hoặc Text (.txt)."
        )

    task_id = str(uuid.uuid4())[:8]
    saved_filename = f"{task_id}_{file.filename}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(saved_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Use user-provided key or server-configured environment key
    effective_key = api_key.strip() if (api_key and api_key.strip()) else os.environ.get("GEMINI_API_KEY", "")

    task_info = {
        "id": task_id,
        "filename": file.filename,
        "original_path": saved_path,
        "file_type": ext.lstrip('.'),
        "source_lang": source_lang,
        "target_lang": target_lang,
        "engine": engine,
        "api_key": effective_key,
        "bilingual": bilingual,
        "status": "preparing",
        "progress_percent": 0.0,
        "total_paragraphs": 0,
        "completed_paragraphs": 0,
        "total_words": 0,
        "completed_words": 0,
        "estimated_pages": 1,
        "speed_wpm": 0,
        "start_time": time.time(),
        "elapsed_seconds": 0,
        "eta_seconds": None,
        "recent_logs": [],
        "translated_map": {},
        "error_message": None,
        "output_files": {
            "docx": None,
            "pdf": None,
            "txt": None,
            "docx_bilingual": None
        },
        "_elements": [],
        "_stop_flag": False
    }

    TASKS[task_id] = task_info
    save_task_to_disk(task_id)

    # Launch background thread for non-blocking execution
    worker_thread = threading.Thread(target=run_translation_worker, args=(task_id,), daemon=True)
    worker_thread.start()

    return {
        "task_id": task_id,
        "filename": file.filename,
        "total_paragraphs": 0,
        "total_words": 0,
        "estimated_pages": 1,
        "status": "preparing"
    }


@app.post("/api/test-key")
def test_api_key(engine: str = Form(...), api_key: str = Form(...)):
    """
    Validates the user's API key and returns model status.
    """
    key = api_key.strip()
    if not key:
        return JSONResponse(status_code=400, content={"valid": False, "message": "Vui lòng nhập API Key!"})

    start = time.time()
    try:
        if engine == "gemini":
            models_to_check = ["gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3.5-flash"]
            payload = {
                "contents": [{"parts": [{"text": "Hello"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
            last_err = "Không thể kết nối"
            for m in models_to_check:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
                try:
                    resp = requests.post(url, json=payload, timeout=10)
                    elapsed = round((time.time() - start) * 1000)
                    if resp.status_code == 200:
                        return {"valid": True, "model": m, "latency_ms": elapsed, "message": f"Kết nối Gemini ({m}) thành công ({elapsed}ms)! Tốc độ: ~300 trang/phút."}
                    last_err = resp.json().get("error", {}).get("message", resp.text[:100])
                except Exception as e:
                    last_err = str(e)
            return JSONResponse(status_code=400, content={"valid": False, "message": f"Key không hợp lệ: {last_err}"})

        elif engine == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            elapsed = round((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"valid": True, "model": "Groq Llama 3.3", "latency_ms": elapsed, "message": f"Kết nối Groq LPU thành công ({elapsed}ms)! Tốc độ: 750 tokens/s."}
            else:
                return JSONResponse(status_code=400, content={"valid": False, "message": f"Key Groq không hợp lệ: {resp.text[:100]}"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"valid": False, "message": f"Lỗi kết nối: {str(e)}"})

    return JSONResponse(status_code=400, content={"valid": False, "message": "Mô hình không hỗ trợ kiểm tra key."})


@app.get("/api/task/{task_id}")
def get_task_status(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ dịch!")

    # Return safe representation without private keys
    return {
        "id": task["id"],
        "filename": task["filename"],
        "status": task["status"],
        "progress_percent": task.get("progress_percent", 0),
        "total_paragraphs": task.get("total_paragraphs", 0),
        "completed_paragraphs": task.get("completed_paragraphs", 0),
        "total_words": task.get("total_words", 0),
        "completed_words": task.get("completed_words", 0),
        "estimated_pages": task.get("estimated_pages", 1),
        "speed_wpm": task.get("speed_wpm", 0),
        "elapsed_seconds": task.get("elapsed_seconds", 0),
        "eta_seconds": task.get("eta_seconds"),
        "recent_logs": task.get("recent_logs", []),
        "output_files": task.get("output_files", {}),
        "error_message": task.get("error_message")
    }


@app.get("/api/task/{task_id}/events")
async def stream_task_events(task_id: str):
    """
    Server-Sent Events endpoint for real-time progress updates.
    """
    async def event_generator():
        while True:
            task = TASKS.get(task_id)
            if not task:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            data = {
                "id": task["id"],
                "status": task["status"],
                "progress_percent": task.get("progress_percent", 0),
                "total_paragraphs": task.get("total_paragraphs", 0),
                "completed_paragraphs": task.get("completed_paragraphs", 0),
                "total_words": task.get("total_words", 0),
                "completed_words": task.get("completed_words", 0),
                "speed_wpm": task.get("speed_wpm", 0),
                "elapsed_seconds": task.get("elapsed_seconds", 0),
                "eta_seconds": task.get("eta_seconds"),
                "recent_logs": task.get("recent_logs", [])[-5:],
                "output_files": task.get("output_files", {}),
                "error_message": task.get("error_message")
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            if task["status"] in ["completed", "error", "stopped"]:
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/task/{task_id}/content")
def get_task_content(task_id: str):
    """
    Returns original and translated elements for interactive side-by-side reading.
    """
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ!")

    elements = task.get("_elements", [])
    trans_map = task.get("translated_map", {})

    items = []
    for elem in elements:
        elem_id = str(elem["id"])
        items.append({
            "id": elem["id"],
            "type": elem.get("type", "paragraph"),
            "original": elem.get("text", ""),
            "translated": trans_map.get(elem_id, ""),
            "style": elem.get("style", "Normal")
        })

    return {
        "filename": task["filename"],
        "status": task["status"],
        "items": items
    }


@app.get("/api/task/{task_id}/download/{format_type}")
def download_result(task_id: str, format_type: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ!")

    output_files = task.get("output_files", {})
    file_name = output_files.get(format_type)

    if not file_name:
        raise HTTPException(status_code=404, detail=f"Chưa có tệp định dạng {format_type}!")

    file_path = os.path.join(OUTPUT_DIR, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Tệp không tồn tại trên hệ thống!")

    download_name = file_name
    # Strip internal task_id prefix if present for clean download name
    if download_name.startswith(f"{task_id}_"):
        download_name = download_name[len(task_id) + 1:]

    return FileResponse(
        path=file_path,
        filename=download_name,
        media_type="application/octet-stream"
    )


@app.post("/api/task/{task_id}/stop")
def stop_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Không tìm thấy tác vụ!")
    task["_stop_flag"] = True
    task["status"] = "stopped"
    save_task_to_disk(task_id)
    return {"message": "Đã gửi lệnh dừng tác vụ!"}


@app.get("/api/tasks")
def list_tasks():
    """
    Returns list of all recent translations for history overview.
    """
    results = []
    for t_id, task in TASKS.items():
        results.append({
            "id": task["id"],
            "filename": task["filename"],
            "status": task["status"],
            "progress_percent": task.get("progress_percent", 0),
            "total_words": task.get("total_words", 0),
            "total_paragraphs": task.get("total_paragraphs", 0),
            "output_files": task.get("output_files", {})
        })
    return results


@app.delete("/api/task/{task_id}")
def delete_task(task_id: str):
    if task_id in TASKS:
        task = TASKS.pop(task_id)
        # Delete task file
        json_path = os.path.join(TASKS_DIR, f"{task_id}.json")
        if os.path.exists(json_path):
            os.remove(json_path)
    return {"message": "Đã xóa tác vụ!"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
