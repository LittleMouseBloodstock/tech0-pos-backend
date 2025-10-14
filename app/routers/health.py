from __future__ import annotations

from typing import Dict

from fastapi import APIRouter
from ..db import engine
from ..models import Base


router = APIRouter()


@router.get("/health")
def health() -> Dict[str, str]:
    # Ensure tables exist (no-op if already created)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
    return {"status": "ok"}
