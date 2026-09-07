import os
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

RIPPLE_BASE_DIR = Path(os.getenv("RIPPLE_BASE_DIR", "/srv/projects/ripple_server"))

REALTIME_DIR = RIPPLE_BASE_DIR / "audio-uploader" / "realtime-uploads"
REALTIME_DIR.mkdir(parents=True, exist_ok=True)
TRAINING_DIR = RIPPLE_BASE_DIR / "audio-uploader" / "training-uploads"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
API_KEY = os.environ["UPLOAD_API_KEY"]
RESULTS_FILE = RIPPLE_BASE_DIR / "environment-uploader" / "realtime-uploads" / "latest.json"

app = FastAPI()

def check_key(x_api_key: str):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="bad api key")

def get_latest(dest_dir: Path) -> Path:
    files = [f for f in dest_dir.iterdir() if f.is_file]
    if not files:
        raise HTTPException(status_code=404, detail="no files")
    return max(files, key=lambda f: f.stat().st_mtime)

async def save_upload(dest_dir: Path, filename: str, request: Request, x_api_key: str):
    check_key(x_api_key)
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="bad filename")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty body")
    dest = dest_dir / filename
    dest.write_bytes(body)
    return {"filename": filename, "bytes": len(body)}

class ConnectionManager:
    def __init__(self):
        self.active: set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, message: str):
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

manager = ConnectionManager()
_last_mtime = None

async def watch_results_file():
    global _last_mtime
    while True:
        try:
            mtime = os.path.getmtime(RESULTS_FILE)
            if _last_mtime is None:
                _last_mtime = mtime
            elif mtime != _last_mtime:
                _last_mtime = mtime
                with open(RESULTS_FILE) as f:
                    await manager.broadcast(f.read())
        except FileNotFoundError:
            pass
        await asyncio.sleep(1)

@app.on_event("startup")
async def start_watcher():
    asyncio.create_task(watch_results_file())

@app.websocket("/realtime/ws/results")
async def results_ws(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE) as f:
                await websocket.send_text(f.read())
        while True:
            await websocket.receive_text()  # keeps connection alive; ignores client pings
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.put("/realtime/{filename}")
async def upload_realtime(filename: str, request: Request, x_api_key: str = Header(...)):
    return await save_upload(REALTIME_DIR, filename, request, x_api_key)

@app.put("/training/{filename}")
async def upload_training(filename: str, request: Request, x_api_key: str = Header(...)):
    return await save_upload(TRAINING_DIR, filename, request, x_api_key)

@app.get("/training/latest-filename")
async def latest_training(x_api_key: str = Header(...)):
    check_key(x_api_key)
    path = get_latest(TRAINING_DIR)
    return PlainTextResponse(path.stem)
