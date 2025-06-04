from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import threading
from pathlib import Path
from file_store import load_benchmark_details, load_all_benchmarks_with_models

from app import AppLogic
from ui_bridge import DataChangeType

app = FastAPI()

# Global variables for event loop management
event_loop = None
manager = None

@app.on_event("startup")
async def startup_event():
    global event_loop, manager
    event_loop = asyncio.get_event_loop()
    manager = WebSocketManager()

class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if self.active_connections:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for connection in disconnected:
                self.disconnect(connection)

class WSBridge:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    # Core UI operations - these are no-ops for API mode
    def show_message(self, level: str, title: str, message: str) -> None:
        print(f"[{level.upper()}] {title}: {message}")

    def update_status_bar(self, message: str, timeout: int = 0) -> None:
        print(f"Status: {message}")

    def clear_console_log(self) -> None:
        pass

    def update_console_log(self, text: str) -> None:
        print(f"Console: {text}")

    # Navigation - no-ops for API mode
    def show_home_page(self) -> None:
        pass

    def show_composer_page(self) -> None:
        pass

    def show_console_page(self) -> None:
        pass

    # Data population - no-ops for API mode
    def populate_composer_table(self, rows: list) -> None:
        pass

    def display_benchmark_summary_in_console(self, result: dict, run_id: str) -> None:
        print(f"Benchmark summary for run {run_id}: {result}")

    def display_full_benchmark_details_in_console(self, details: dict) -> None:
        print(f"Benchmark details: {details}")

    def populate_home_benchmarks_table(self, benchmarks_data: list) -> None:
        pass

    # Auto refresh - no-ops for API mode
    def start_auto_refresh(self, interval_ms: int = 1000) -> None:
        pass

    def stop_auto_refresh(self) -> None:
        pass

    # Observer pattern - no-ops for API mode
    def register_data_callback(self, change_type, callback) -> None:
        pass

    def unregister_data_callback(self, change_type, callback) -> None:
        pass

    # Data refresh triggers - no-ops for API mode
    def refresh_home_page_data(self) -> None:
        pass

    def refresh_composer_page_data(self) -> None:
        pass

    def refresh_console_page_data(self) -> None:
        pass

    def get_csv_file_path_via_dialog(self):
        return None

    # Real notification methods that use WebSocket
    def notify_benchmark_progress(self, job_id: int, progress_data: dict):
        try:
            if event_loop and manager:
                # Use asyncio.run_coroutine_threadsafe for thread-safe async call
                future = asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "benchmark-progress", "job_id": job_id, **progress_data}),
                    event_loop
                )
                # Don't wait for the result to avoid blocking
        except Exception as e:
            print(f"Error broadcasting benchmark progress: {e}")

    def notify_benchmark_complete(self, job_id: int, result_summary: dict):
        try:
            if event_loop and manager:
                future = asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "benchmark-complete", "job_id": job_id, **result_summary}),
                    event_loop
                )
        except Exception as e:
            print(f"Error broadcasting benchmark complete: {e}")

    def notify_data_change(self, change_type: DataChangeType, data: dict | None):
        try:
            if event_loop and manager:
                future = asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": change_type.name.lower(), "data": data}),
                    event_loop
                )
        except Exception as e:
            print(f"Error broadcasting data change: {e}")

    def notify_active_benchmarks_updated(self, active_benchmarks_data: dict):
        try:
            if event_loop and manager:
                future = asyncio.run_coroutine_threadsafe(
                    manager.broadcast({"event": "active_benchmarks_updated", "data": active_benchmarks_data}),
                    event_loop
                )
        except Exception as e:
            print(f"Error broadcasting active benchmarks: {e}")

bridge = WSBridge()
logic = AppLogic(ui_bridge=bridge)

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "Backend is running"}

@app.post("/launch")
async def launch_benchmark(payload: dict):
    return logic.launch_benchmark_run(
        payload.get("prompts", []),
        payload.get("pdfPaths", []),
        payload.get("modelNames", []),
        payload.get("benchmarkName", ""),
        payload.get("benchmarkDescription", ""),
        payload.get("webSearchEnabled", False)
    )

@app.get("/benchmarks/all")
async def list_benchmarks():
    benchmarks = load_all_benchmarks_with_models(db_path=Path(__file__).parent)
    if hasattr(logic, 'get_active_benchmarks_info'):
        active_benchmarks = logic.get_active_benchmarks_info()
        for benchmark in benchmarks:
            benchmark_id = benchmark.get('id')
            for job_id, job_info in active_benchmarks.items():
                if job_info.get('benchmark_id') == benchmark_id:
                    benchmark['status'] = 'in-progress'
                    break
    return benchmarks

@app.get("/benchmarks/{benchmark_id}")
async def get_benchmark_details(benchmark_id: int):
    details = load_benchmark_details(benchmark_id, db_path=Path(__file__).parent)
    if details is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return details

@app.post("/delete")
async def delete_benchmark_endpoint(payload: dict):
    benchmark_id = payload.get("benchmarkId") or payload.get("benchmark_id")
    return logic.handle_delete_benchmark(int(benchmark_id))

@app.post("/rerun-prompt")
async def rerun_prompt_endpoint(payload: dict):
    prompt_id = payload.get("promptId") or payload.get("prompt_id")
    if not prompt_id:
        raise HTTPException(status_code=400, detail="prompt_id is required")
    return logic.rerun_single_prompt(int(prompt_id))

@app.post("/update")
async def update_benchmark_endpoint(payload: dict):
    benchmark_id = payload.get("benchmarkId") or payload.get("benchmark_id")
    new_label = payload.get("newLabel") or payload.get("new_label")
    new_description = payload.get("newDescription") or payload.get("new_description")
    return logic.handle_update_benchmark_details(int(benchmark_id), new_label, new_description)

@app.get("/benchmarks/{benchmark_id}/sync-status")
async def get_benchmark_sync_status(benchmark_id: int):
    """Get sync status for a benchmark."""
    return logic.handle_get_sync_status(benchmark_id)

@app.post("/benchmarks/{benchmark_id}/sync")
async def sync_benchmark(benchmark_id: int):
    """Sync a benchmark by rerunning missing, failed, or pending prompts."""
    return logic.handle_sync_benchmark(benchmark_id)

@app.get("/models")
async def list_models():
    return [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-4.1-mini",
        "o3",
        "o4-mini",
        "claude-opus-4-20250514",
        "claude-opus-4-20250514-thinking",
        "claude-sonnet-4-20250514",
        "claude-sonnet-4-20250514-thinking",
        "claude-3-7-sonnet-20250219",
        "claude-3-7-sonnet-20250219-thinking",
        "claude-3-5-haiku-20241022",
        "gemini-2.5-flash-preview-05-20",
        "gemini-2.5-pro-preview-05-06",
    ]

@app.get("/benchmarks/{benchmark_id}/export")
async def export_csv(benchmark_id: int):
    import tempfile
    import os
    import re
    
    # Get benchmark details to use the actual name
    try:
        benchmark_details = load_benchmark_details(benchmark_id, db_path=Path(__file__).parent)
        if not benchmark_details:
            raise HTTPException(status_code=404, detail="Benchmark not found")
        
        # Use the actual benchmark name, sanitized for filename
        benchmark_name = benchmark_details.get('label', f'benchmark_{benchmark_id}')
        # Sanitize filename by removing/replacing invalid characters
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', benchmark_name)
        safe_name = safe_name.strip().replace(' ', '_')
        if not safe_name:  # Fallback if name becomes empty after sanitization
            safe_name = f'benchmark_{benchmark_id}'
            
    except Exception:
        # Fallback to generic name if we can't get benchmark details
        safe_name = f'benchmark_{benchmark_id}'
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
        temp_filename = temp_file.name
    
    try:
        # Use the more detailed export method that accepts a filename
        result = logic.handle_export_benchmark_csv(benchmark_id, temp_filename)
        
        # Create an async cleanup function
        async def cleanup_temp_file():
            try:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            except Exception:
                pass  # Ignore cleanup errors
        
        # Return the file with the actual benchmark name
        response_filename = f"{safe_name}.csv"
        return FileResponse(
            temp_filename, 
            media_type="text/csv", 
            filename=response_filename,
            background=cleanup_temp_file  # Pass the async function directly
        )
    except Exception as e:
        # Clean up temp file if there's an error
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ===== PROMPT SET ENDPOINTS =====

@app.post("/prompt-sets")
async def create_prompt_set(payload: dict):
    """Create a new prompt set."""
    name = payload.get("name", "")
    description = payload.get("description", "")
    prompts = payload.get("prompts", [])
    
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not prompts:
        raise HTTPException(status_code=400, detail="At least one prompt is required")
    
    return logic.handle_create_prompt_set(name, description, prompts)

@app.get("/prompt-sets")
async def get_prompt_sets():
    """Get all prompt sets."""
    return logic.handle_get_prompt_sets()

@app.get("/prompt-sets/next-number")
async def get_next_prompt_set_number():
    """Get the next available prompt set number."""
    return logic.handle_get_next_prompt_set_number()

@app.get("/prompt-sets/{prompt_set_id}")
async def get_prompt_set_details(prompt_set_id: int):
    """Get details of a specific prompt set."""
    result = logic.handle_get_prompt_set_details(prompt_set_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Prompt set not found")
    return result

@app.put("/prompt-sets/{prompt_set_id}")
async def update_prompt_set(prompt_set_id: int, payload: dict):
    """Update an existing prompt set."""
    name = payload.get("name", "")
    description = payload.get("description", "")
    prompts = payload.get("prompts", [])
    
    return logic.handle_update_prompt_set(prompt_set_id, name, description, prompts)

@app.delete("/prompt-sets/{prompt_set_id}")
async def delete_prompt_set(prompt_set_id: int):
    """Delete a prompt set."""
    return logic.handle_delete_prompt_set(prompt_set_id)

# ===== FILE MANAGEMENT ENDPOINTS =====

@app.post("/files/upload")
async def upload_file(payload: dict):
    """Upload and register a file in the system."""
    file_path = payload.get("filePath", "")
    
    if not file_path:
        raise HTTPException(status_code=400, detail="File path is required")
    
    return logic.handle_upload_file(file_path)

@app.get("/files")
async def get_files():
    """Get all registered files."""
    return logic.handle_get_files()

@app.get("/files/{file_id}")
async def get_file_details(file_id: int):
    """Get details of a specific file."""
    result = logic.handle_get_file_details(file_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="File not found")
    return result

@app.delete("/files/{file_id}")
async def delete_file(file_id: int):
    """Delete a file from the system."""
    return logic.handle_delete_file(file_id)

@app.post("/validate-tokens")
async def validate_tokens(payload: dict):
    return logic.handle_validate_tokens(
        payload.get("prompts", []),
        payload.get("pdfPaths", []) or payload.get("file_paths", []),  # Support both parameter names
        payload.get("modelNames", []) or payload.get("model_names", [])  # Support both parameter names
    )

# ===== VECTOR SEARCH ENDPOINTS =====

@app.post("/vector-stores")
async def create_vector_store(payload: dict):
    """Create a new vector store."""
    return logic.handle_create_vector_store(
        name=payload.get("name"),
        description=payload.get("description"),
        file_ids=payload.get("file_ids", []),
        expires_after_days=payload.get("expires_after_days")
    )

@app.get("/vector-stores")
async def get_vector_stores():
    """Get all vector stores."""
    return logic.handle_get_vector_stores()

@app.get("/vector-stores/{vector_store_id}")
async def get_vector_store_details(vector_store_id: str):
    """Get details of a specific vector store."""
    return logic.handle_get_vector_store_details(vector_store_id)

@app.post("/vector-stores/{vector_store_id}/files")
async def add_files_to_vector_store(vector_store_id: str, payload: dict):
    """Add files to an existing vector store."""
    return logic.handle_add_files_to_vector_store(
        vector_store_id=vector_store_id,
        file_ids=payload.get("file_ids", [])
    )

@app.post("/vector-stores/{vector_store_id}/search")
async def search_vector_store(vector_store_id: str, payload: dict):
    """Search a vector store directly."""
    return logic.handle_search_vector_store(
        vector_store_id=vector_store_id,
        query=payload.get("query"),
        max_results=payload.get("max_results", 10)
    )

@app.post("/vector-stores/ask")
async def ask_vector_stores(payload: dict):
    """Ask a question using vector search across multiple stores."""
    return logic.handle_ask_vector_store(
        vector_store_ids=payload.get("vector_store_ids", []),
        question=payload.get("question"),
        model=payload.get("model", "gpt-4o-mini"),
        max_results=payload.get("max_results", 20)
    )

@app.delete("/vector-stores/{vector_store_id}")
async def delete_vector_store(vector_store_id: str):
    """Delete a vector store."""
    return logic.handle_delete_vector_store(vector_store_id)

@app.post("/benchmarks/{benchmark_id}/vector-stores")
async def associate_benchmark_vector_store(benchmark_id: int, payload: dict):
    """Associate a benchmark with a vector store."""
    return logic.handle_associate_benchmark_vector_store(
        benchmark_id=benchmark_id,
        vector_store_id=payload.get("vector_store_id")
    )

@app.get("/benchmarks/{benchmark_id}/vector-stores")
async def get_benchmark_vector_stores(benchmark_id: int):
    """Get vector stores associated with a benchmark."""
    return logic.handle_get_benchmark_vector_stores(benchmark_id)

@app.post("/reset-stuck-benchmarks")
async def reset_stuck_benchmarks_endpoint():
    """Reset benchmarks that are stuck in running/in-progress state."""
    try:
        from file_store import reset_stuck_benchmarks
        from pathlib import Path
        
        db_path = Path(__file__).parent
        reset_count = reset_stuck_benchmarks(db_path)
        
        # Also clean up any jobs in the AppLogic instance
        if hasattr(logic, 'jobs'):
            stuck_jobs = []
            for job_id, job_data in list(logic.jobs.items()):
                # Remove jobs that have been running for more than an hour
                if job_data.get('start_time'):
                    try:
                        from datetime import datetime, timedelta
                        start_time = datetime.fromisoformat(job_data['start_time'].replace('Z', '+00:00'))
                        if datetime.now() - start_time > timedelta(hours=1):
                            stuck_jobs.append(job_id)
                    except:
                        # If we can't parse the time, consider it stuck
                        stuck_jobs.append(job_id)
            
            for job_id in stuck_jobs:
                if job_id in logic.jobs:
                    logic.jobs[job_id]['status'] = 'error'
                    # Try to stop the worker if it exists
                    worker = logic.jobs[job_id].get('worker')
                    if worker and hasattr(worker, 'active'):
                        worker.active = False
                    del logic.jobs[job_id]
        
        message = f"Reset {reset_count} stuck benchmarks" + (f" and cleaned up {len(stuck_jobs)} stuck jobs" if 'stuck_jobs' in locals() and stuck_jobs else "")
        
        return {
            "success": True, 
            "message": message,
            "reset_count": reset_count,
            "cleaned_jobs": len(stuck_jobs) if 'stuck_jobs' in locals() else 0
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
