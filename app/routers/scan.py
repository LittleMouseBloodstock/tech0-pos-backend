from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, File, UploadFile
from PIL import Image, ImageOps


router = APIRouter()


@router.post("/scan")
async def scan(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Decode barcodes from uploaded image and return first code and all codes.
    Returns: { code: str|None, codes: [str] }
    """
    content = await file.read()
    img = Image.open(BytesIO(content)).convert("L")  # grayscale
    # Preprocess: autocontrast + upscaling to improve detection on small images
    img = ImageOps.autocontrast(img)
    w, h = img.size
    if max(w, h) < 900:
        scale = max(2, 900 // max(w, h))
        img = img.resize((w * scale, h * scale))
    # Lazy import to avoid hard dependency at startup
    try:
        from pyzbar.pyzbar import decode as zbar_decode  # type: ignore
    except Exception:
        return {"code": None, "codes": [], "error": "pyzbar not installed"}
    # Try multiple rotations to improve robustness
    codes: List[str] = []
    for angle in (0, 90, 180, 270):
        im = img.rotate(angle, expand=True) if angle else img
        results = zbar_decode(im)
        if not results:
            continue
        for r in results:
            try:
                codes.append(r.data.decode("utf-8"))
            except Exception:
                codes.append(r.data.decode("latin-1", errors="ignore"))
        if codes:
            break
    return {"code": codes[0] if codes else None, "codes": codes}

from io import BytesIO
