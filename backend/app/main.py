from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.routers import chat, analysis, invoices, auth, fiscal, fiscal, fiscal

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Fiscalía IA — Asesor Financiero para Autónomos",
    description="API completa para gestión fiscal de autónomos en España",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat IA"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Análisis Financiero"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Facturas"])
app.include_router(fiscal.router, prefix="/api/fiscal", tags=["Información Fiscal"])
app.include_router(fiscal.router, prefix="/api/fiscal", tags=["Calendario Fiscal"])


app.include_router(fiscal.router, prefix="/api/fiscal", tags=["Calendario Fiscal"])


@app.get("/")
def root():
    return {
        "app": "Fiscalía IA",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }
