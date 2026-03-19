from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.routers import chat, analysis, invoices, auth, fiscal, admin, stripe_router, spreadsheets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    await init_db()
    # Initialize RAG knowledge base
    try:
        from app.services.rag_service import initialize_knowledge_base
        await initialize_knowledge_base()
    except Exception as e:
        print(f"[RAG] Warning: Could not initialize knowledge base: {e}")
    yield


app = FastAPI(
    title="FiscalIA — Asesor Financiero y Fiscal España",
    description="IA con RAG para asesoramiento fiscal y financiero en España",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://fiscalia-frontend.onrender.com",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5500",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Admin-Key"],
)

app.include_router(auth.router,           prefix="/api/auth",        tags=["Auth"])
app.include_router(chat.router,           prefix="/api/chat",        tags=["Chat RAG"])
app.include_router(analysis.router,       prefix="/api/analysis",    tags=["Análisis"])
app.include_router(invoices.router,       prefix="/api/invoices",    tags=["Facturas"])
app.include_router(fiscal.router,         prefix="/api/fiscal",      tags=["Fiscal"])
app.include_router(admin.router,          prefix="/api/admin",       tags=["Admin"])
app.include_router(stripe_router.router,  prefix="/api/stripe",      tags=["Pagos"])
app.include_router(spreadsheets.router,   prefix="/api/spreadsheets",tags=["Excel/CSV"])


@app.get("/")
def root():
    return {"app": "FiscalIA", "version": "3.0.0", "status": "online", "mode": "RAG"}


@app.get("/api/rag/status")
async def rag_status():
    """Check RAG knowledge base status."""
    try:
        from app.services.rag_service import get_collection
        col = get_collection()
        count = col.count()
        return {"status": "ok", "documents": count, "mode": "ChromaDB + Web"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
