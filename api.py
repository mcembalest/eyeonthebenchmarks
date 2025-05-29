from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
import asyncio
from pathlib import Path
from file_store import load_benchmark_details, load_all_benchmarks_with_models

from app import AppLogic
from ui_bridge import DataChangeType

app = FastAPI()
event_loop: asyncio.AbstractEventLoop | None = None

@app.on_event("startup")
async def startup_event():
    global event_loop
    event_loop = asyncio.get_running_loop()

class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = WebSocketManager()

class WSBridge:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def notify_benchmark_progress(self, job_id: int, progress_data: dict):
        if event_loop:
            event_loop.call_soon_threadsafe(asyncio.create_task, manager.broadcast({"event": "benchmark-progress", **progress_data}))
        else:
            asyncio.create_task(manager.broadcast({"event": "benchmark-progress", **progress_data}))

    def notify_benchmark_complete(self, job_id: int, result_summary: dict):
        if event_loop:
            event_loop.call_soon_threadsafe(asyncio.create_task, manager.broadcast({"event": "benchmark-complete", **result_summary}))
        else:
            asyncio.create_task(manager.broadcast({"event": "benchmark-complete", **result_summary}))

    def notify_data_change(self, change_type: DataChangeType, data: dict | None):
        if event_loop:
            event_loop.call_soon_threadsafe(asyncio.create_task, manager.broadcast({"event": change_type.name.lower(), "data": data}))
        else:
            asyncio.create_task(manager.broadcast({"event": change_type.name.lower(), "data": data}))

bridge = WSBridge()
logic = AppLogic(ui_bridge=bridge)

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
    """Validate token limits for given prompts, files, and models."""
    prompts = payload.get("prompts", [])
    file_paths = payload.get("filePaths", [])
    model_names = payload.get("modelNames", [])
    
    return logic.handle_validate_tokens(prompts, file_paths, model_names)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000)
