import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File

from backend.config import settings

router = APIRouter(prefix="/api/assets", tags=["assets"])

ALLOWED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "image.png")[1].lower()
    if ext not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported image type: {ext}")

    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    safe_name = f"{timestamp}_{unique_id}{ext}"

    assets_dir = settings.KNOWLEDGE_DIR / "_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    dest = assets_dir / safe_name
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    # Return relative path for markdown embedding
    rel_path = f"_assets/{safe_name}"
    return {"path": rel_path, "url": f"/api/assets/files/{safe_name}"}
