from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health
from .routers import products, scan
from .routers import purchase_v2 as purchase
from .core.config import get_settings
from .db import engine
from .models import Base


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

# CORS (origins from env, default localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple startup log to help diagnose CORS configuration in Azure logs
@app.on_event("startup")
def _log_cors_settings() -> None:  # pragma: no cover
    try:
        import logging

        logging.getLogger("uvicorn.error").info(
            "CORS allow_origins=%s allow_origin_regex=%s",
            settings.allowed_origins,
            settings.allowed_origin_regex,
        )
    except Exception:
        pass

app.include_router(health.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(purchase.router, prefix="/api")
app.include_router(scan.router, prefix="/api")


@app.get("/")
def root_index() -> dict:
    return {
        "message": "Backend is running.",
        "api_health": "/api/health",
        "api_root": "/api",
        "name": settings.app_name,
        "version": "0.1.0",
    }

@app.get("/api")
def root() -> dict:
    return {"name": settings.app_name, "version": "0.1.0"}


@app.on_event("startup")
def on_startup() -> None:
    # Auto-create tables (dev/demo). In production, use migrations.
    Base.metadata.create_all(bind=engine)
