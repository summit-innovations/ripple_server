import os
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Header

API_KEY = os.environ["UPLOAD_API_KEY"]
UPLOAD_DIR = Path("/srv/projects/ripple_server/audio-uploader/training-uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()

@app.put("/upload/{filename}")
async def upload(filename: str, request: Request, x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="bad api key")

    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="bad filename")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty body")

    dest = UPLOAD_DIR / filename
    dest.write_bytes(body)

    return {"filename": filename, "bytes": len(body)}
