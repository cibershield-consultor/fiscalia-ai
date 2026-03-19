"""FiscalIA — Entry point principal con seguridad mejorada."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.database import init_db
from app.core.logging import logger
from app.routers import chat, analysis, invoices, auth, fiscal, admin, stripe_router, spreadsheets, excel_ai

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando FiscalIA v4.0...")
    await init_db()
    logger.info("Base de datos inicializada")
    try:
        from app.services.rag_service import initialize_knowledge_base
        await initialize_knowledge_base()
        logger.info("Base de conocimiento RAG cargada")
    except Exception as e:
        logger.warning(f"RAG no disponible: {e}")
    yield
    logger.info("FiscalIA apagado")

app = FastAPI(
    title="FiscalIA — Asesor Fiscal España",
    description="IA con RAG para asesoramiento fiscal y financiero en España",
    version="4.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS seguro — sin "null"
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://fiscalia-frontend.onrender.com,http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:5500"
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Admin-Key"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    ms = (time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} [{ms:.0f}ms]")
    return response

app.include_router(auth.router,           prefix="/api/auth",         tags=["Auth"])
app.include_router(chat.router,           prefix="/api/chat",         tags=["Chat RAG"])
app.include_router(analysis.router,       prefix="/api/analysis",     tags=["Analisis"])
app.include_router(invoices.router,       prefix="/api/invoices",     tags=["Facturas"])
app.include_router(fiscal.router,         prefix="/api/fiscal",       tags=["Fiscal"])
app.include_router(admin.router,          prefix="/api/admin",        tags=["Admin"])
app.include_router(stripe_router.router,  prefix="/api/stripe",       tags=["Pagos"])
app.include_router(spreadsheets.router,   prefix="/api/spreadsheets", tags=["Excel/CSV"])
app.include_router(excel_ai.router,       prefix="/api/excel-ai",     tags=["IA Excel"])

@app.get("/")
def root():
    return {"app": "FiscalIA", "version": "4.0.0", "status": "online"}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "4.0.0"}
