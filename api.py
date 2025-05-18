from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
import asyncio
import json
from pathlib import Path
from file_store import load_benchmark_details
from available_models import get_available_models_as_list

# Import your existing application logic and enums
from app import AppLogic
from ui_bridge import DataChangeType

app = FastAPI()
# Placeholder for event loop to schedule cross-thread tasks
event_loop: asyncio.AbstractEventLoop | None = None

@app.on_event("startup")
async def startup_event():
    global event_loop
    event_loop = asyncio.get_running_loop()

# Manage WebSocket connections for streaming events
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

# Bridge that forwards AppLogic events to WebSocket clients
class WSBridge:
    def __getattr__(self, name):
        # No-op for unused UIBridge methods
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

# Instantiate a single AppLogic with WebSocket bridge
bridge = WSBridge()
logic = AppLogic(ui_bridge=bridge)

# HTTP endpoint to launch a benchmark asynchronously
@app.post("/launch")
async def launch_benchmark(payload: dict):
    return logic.launch_benchmark_run(
        payload.get("prompts", []),
        payload.get("pdfPath", ""),
        payload.get("modelNames", []),
        payload.get("benchmarkName", ""),
        payload.get("benchmarkDescription", ""),
    )

# HTTP endpoint to list all benchmarks (including active)
@app.get("/benchmarks/all")
async def list_benchmarks():
    return logic.list_benchmarks()

# HTTP endpoint to get benchmark details
@app.get("/benchmarks/{benchmark_id}")
async def get_benchmark_details(benchmark_id: int):
    details = load_benchmark_details(benchmark_id, db_path=Path(__file__).parent)
    if details is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return details

# HTTP endpoint to delete a benchmark
@app.post("/delete")
async def delete_benchmark_endpoint(payload: dict):
    benchmark_id = payload.get("benchmarkId") or payload.get("benchmark_id")
    return logic.handle_delete_benchmark(int(benchmark_id))

# HTTP endpoint to update benchmark details
@app.post("/update")
async def update_benchmark_endpoint(payload: dict):
    benchmark_id = payload.get("benchmarkId") or payload.get("benchmark_id")
    new_label = payload.get("newLabel") or payload.get("new_label")
    new_description = payload.get("newDescription") or payload.get("new_description")
    return logic.handle_update_benchmark_details(int(benchmark_id), new_label, new_description)

# HTTP endpoint to list models
@app.get("/models")
async def list_models():
    return get_available_models_as_list()

# HTTP endpoint to export a benchmark as CSV
@app.get("/benchmarks/{benchmark_id}/export")
async def export_csv(benchmark_id: int):
    filename = f"benchmark_{benchmark_id}.csv"
    logic.handle_export_benchmark_csv(benchmark_id, filename)
    return FileResponse(filename, media_type="text/csv", filename=filename)

# WebSocket endpoint for real-time progress and completion events
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open; ignore any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000)
