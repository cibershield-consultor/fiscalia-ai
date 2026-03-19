"""
Fiscalía IA — Endpoints de administración
Protegidos con ADMIN_SECRET_KEY (variable de entorno)
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

router = APIRouter()


def verify_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Clave de administrador incorrecta")


class GrantPremiumRequest(BaseModel):
    email: EmailStr
    days: Optional[int] = None   # None = sin expiración, 30 = 30 días


@router.post("/grant-premium")
async def grant_premium(
    req: GrantPremiumRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Activa Premium a un usuario por email. Puede ser permanente o con fecha de expiración."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {req.email} no encontrado")

    user.plan = "premium"
    user.plan_expires_at = datetime.utcnow() + timedelta(days=req.days) if req.days else None
    await db.commit()

    return JSONResponse(content={
        "ok": True,
        "email": user.email,
        "plan": "premium",
        "expires_at": str(user.plan_expires_at) if user.plan_expires_at else "nunca",
        "message": f"✅ Premium activado para {user.email}" + (f" durante {req.days} días" if req.days else " sin expiración"),
    })


@router.post("/revoke-premium")
async def revoke_premium(
    email: EmailStr,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Revoca Premium y vuelve al plan gratuito."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.plan = "free"
    user.plan_expires_at = None
    await db.commit()

    return JSONResponse(content={"ok": True, "email": user.email, "plan": "free"})


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Lista todos los usuarios registrados."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [{
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "plan": u.plan,
        "plan_expires_at": str(u.plan_expires_at) if u.plan_expires_at else None,
        "created_at": str(u.created_at),
        "messages_today": u.messages_today,
    } for u in users]


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin),
):
    """Estadísticas generales de la plataforma."""
    result = await db.execute(select(User))
    users = result.scalars().all()
    total = len(users)
    premium = sum(1 for u in users if u.plan == "premium")
    return {
        "total_users": total,
        "premium_users": premium,
        "free_users": total - premium,
        "conversion_rate": f"{premium/total*100:.1f}%" if total > 0 else "0%",
    }


@router.get("/rag/stats")
async def rag_stats(_: str = Depends(verify_admin)):
    """Check RAG knowledge base status."""
    from app.rag.vector_store import get_stats
    return get_stats()


@router.post("/rag/reload")
async def rag_reload(_: str = Depends(verify_admin)):
    """Force reload of RAG knowledge base."""
    import asyncio
    from app.rag.vector_store import load_knowledge_base
    chunks = await asyncio.get_event_loop().run_in_executor(None, lambda: load_knowledge_base(force_reload=True))
    return {"ok": True, "chunks_loaded": chunks}


@router.post("/rag/add-document")
async def rag_add_doc(
    doc_id: str,
    title: str,
    content: str,
    source: str = "",
    category: str = "custom",
    _: str = Depends(verify_admin),
):
    """Add a custom document to the RAG knowledge base."""
    import asyncio
    from app.rag.vector_store import add_custom_document
    chunks = await asyncio.get_event_loop().run_in_executor(
        None, lambda: add_custom_document(doc_id, title, content, source, category)
    )
    return {"ok": True, "chunks_added": chunks}

@router.post("/grant-all-premium")
async def grant_all_users_premium(
    days: int = 60,
    x_admin_key: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Give ALL users Premium for N days. Requires admin key."""
    if x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Clave de administrador incorrecta")

    from datetime import datetime, timedelta
    from sqlalchemy import select
    expires_at = datetime.utcnow() + timedelta(days=days)

    result = await db.execute(select(User))
    users = result.scalars().all()
    updated = 0
    for user in users:
        if user.plan_expires_at is None or user.plan_expires_at < expires_at:
            user.plan = "premium"
            user.plan_expires_at = expires_at
            updated += 1
    await db.commit()

    return {
        "ok": True,
        "updated": updated,
        "total_users": len(users),
        "premium_until": expires_at.strftime("%d/%m/%Y"),
        "days": days,
    }
