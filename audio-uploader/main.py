import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import PlainTextResponse

API_KEY = os.environ["UPLOAD_API_KEY"]
REALTIME_DIR = Path("/srv/projects/ripple_server/audio-uploader/realtime-uploads")
REALTIME_DIR.mkdir(exist_ok=True)
TRAINING_DIR = Path("/srv/projects/ripple_server/audio-uploader/training-uploads")
TRAINING_DIR.mkdir(exist_ok=True)

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
