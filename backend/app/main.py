from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.routers import chat, analysis, invoices, auth, fiscal


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

# CORS — allow_credentials=True es incompatible con allow_origins=["*"]
# Se listan los orígenes permitidos explícitamente
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://fiscalia-frontend.onrender.com",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5500",  # Live Server de VSCode
        "null",                   # file:// (abrir index.html directamente)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["Autenticación"])
app.include_router(chat.router,     prefix="/api/chat",     tags=["Chat IA"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Análisis Financiero"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Facturas"])
app.include_router(fiscal.router,   prefix="/api/fiscal",   tags=["Información Fiscal"])


@app.get("/")
def root():
    return {
        "app": "Fiscalía IA",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }
