"""
FiscalIA v3.1 — Production-grade FastAPI backend
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.database import init_db
from app.core.logging_config import log
from app.core.rate_limit import limiter
from app.routers import (
    chat, analysis, invoices, auth,
    fiscal, admin, stripe_router, spreadsheets, excel_ai
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("FiscalIA starting up...")
    os.makedirs("logs", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)

    await init_db()
    log.info("Database initialized")

    try:
        from app.services.rag_service import initialize_knowledge_base
        await initialize_knowledge_base()
    except Exception as e:
        log.warning(f"RAG init warning: {e}")

    log.info("FiscalIA ready ✓")
    yield
    log.info("FiscalIA shutting down")


app = FastAPI(
    title="FiscalIA — Asesor Fiscal IA España",
    description="IA con RAG para asesoramiento fiscal y financiero en España",
    version="3.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Rate limiting ─────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "https://fiscalia-frontend.onrender.com",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5500",
    # NOTE: "null" removed — was a security risk in production
]

# In dev, allow all (only when explicitly set)
if os.getenv("ENVIRONMENT") == "development":
    ALLOWED_ORIGINS.append("null")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Admin-Key"],
)

# ── Request logging middleware ─────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Skip logging for health checks
    if request.url.path in ("/", "/health", "/api/health"):
        return await call_next(request)
    log.info(f"{request.method} {request.url.path}")
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            log.warning(f"{request.method} {request.url.path} → {response.status_code}")
        return response
    except Exception as e:
        log.error(f"Unhandled error on {request.url.path}: {e}")
        return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router,            prefix="/api/auth",         tags=["Auth"])
app.include_router(chat.router,            prefix="/api/chat",         tags=["Chat RAG"])
app.include_router(analysis.router,        prefix="/api/analysis",     tags=["Análisis"])
app.include_router(invoices.router,        prefix="/api/invoices",     tags=["Facturas"])
app.include_router(fiscal.router,          prefix="/api/fiscal",       tags=["Fiscal"])
app.include_router(admin.router,           prefix="/api/admin",        tags=["Admin"])
app.include_router(stripe_router.router,   prefix="/api/stripe",       tags=["Pagos"])
app.include_router(spreadsheets.router,    prefix="/api/spreadsheets", tags=["Excel/CSV"])
app.include_router(excel_ai.router,        prefix="/api/excel-ai",     tags=["IA Excel"])

# ── Health & info endpoints ───────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"app": "FiscalIA", "version": "3.1.0", "status": "online"}


@app.get("/health", tags=["Health"])
async def health_check():
    """Full health check — verifies DB and RAG."""
    checks = {"api": "ok", "database": "unknown", "rag": "unknown"}
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        log.error(f"Health check DB error: {e}")

    try:
        from app.services.rag_service import FISCAL_KNOWLEDGE_BASE
        checks["rag"] = f"ok ({len(FISCAL_KNOWLEDGE_BASE)} docs)"
    except Exception as e:
        checks["rag"] = f"error: {str(e)}"

    status_code = 200 if all("ok" in str(v) for v in checks.values()) else 503
    return JSONResponse(content=checks, status_code=status_code)


@app.get("/api/rag/status", tags=["Health"])
async def rag_status():
    from app.services.rag_service import FISCAL_KNOWLEDGE_BASE
    return {
        "status": "ok",
        "mode": "BM25 in-memory + BOE/AEAT/TGSS web",
        "documents": len(FISCAL_KNOWLEDGE_BASE),
        "sources": ["BOE", "AEAT", "TGSS", "LGSS", "DGT", "LGT", "ICAC", "SEPE", "LETA"]
    }
