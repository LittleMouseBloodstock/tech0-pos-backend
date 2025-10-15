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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
