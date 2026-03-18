from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid, traceback
from datetime import datetime
from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.models.invoice import Invoice
from app.models.user import User
from app.services.ai_service import ask_ai

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    user_id: Optional[int] = None
    file_base64: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None


async def build_financial_context(user_id: int, db: AsyncSession) -> str:
    """
    Builds a financial context string from the user's invoices and dashboard data.
    This is injected into the AI's system prompt so it can give personalized answers.
    """
    try:
        result = await db.execute(
            select(Invoice)
            .where(Invoice.user_id == user_id)
            .order_by(Invoice.fecha.desc())
        )
        invoices = result.scalars().all()

        if not invoices:
            return ""

        año_actual = datetime.utcnow().year

        # Filter current year
        this_year = [
            i for i in invoices
            if (i.fecha or i.created_at) and (i.fecha or i.created_at).year == año_actual
        ]

        ingresos = sum(i.base_imponible for i in this_year if i.tipo == "ingreso")
        gastos = sum(i.base_imponible for i in this_year if i.tipo == "gasto")
        gastos_ded = sum(
            i.base_imponible * (i.porcentaje_deduccion / 100)
            for i in this_year if i.tipo == "gasto" and i.deducible
        )
        iva_rep = sum(i.cuota_iva for i in this_year if i.tipo == "ingreso")
        iva_sop = sum(
            i.cuota_iva * (i.porcentaje_deduccion / 100)
            for i in this_year if i.tipo == "gasto" and i.deducible
        )
        beneficio = ingresos - gastos
        margen = (beneficio / ingresos * 100) if ingresos > 0 else 0

        # Category summary
        cats: dict = {}
        for inv in this_year:
            cat = inv.categoria or "otros"
            cats[cat] = cats.get(cat, 0) + inv.base_imponible

        top_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:5]

        # Recent invoices (last 5)
        recent = invoices[:5]
        recent_lines = "\n".join([
            f"  - {inv.tipo.upper()} | {inv.emisor or inv.concepto or 'Sin descripción'} | "
            f"{inv.base_imponible:.2f}€ | {inv.categoria or 'sin categoría'} | "
            f"{'deducible' if inv.deducible else 'no deducible'} | "
            f"{(inv.fecha or inv.created_at).strftime('%d/%m/%Y') if (inv.fecha or inv.created_at) else 'sin fecha'}"
            for inv in recent
        ])

        # Get user plan
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        plan = user.plan if user else "free"

        context = f"""
== DATOS FINANCIEROS REALES DEL USUARIO (año {año_actual}) ==

RESUMEN ECONÓMICO:
- Ingresos totales: {ingresos:.2f}€
- Gastos totales: {gastos:.2f}€
- Beneficio neto: {beneficio:.2f}€
- Margen neto: {margen:.1f}%
- Gastos deducibles: {gastos_ded:.2f}€
- IVA repercutido (a cobrar): {iva_rep:.2f}€
- IVA soportado deducible: {iva_sop:.2f}€
- IVA a ingresar a Hacienda: {max(0, iva_rep - iva_sop):.2f}€
- Total facturas registradas este año: {len(this_year)}
- Plan del usuario: {plan}

PRINCIPALES CATEGORÍAS DE GASTO/INGRESO:
{chr(10).join(f"  - {cat}: {amt:.2f}€" for cat, amt in top_cats)}

ÚLTIMAS 5 FACTURAS:
{recent_lines if recent_lines else "  Sin facturas recientes"}

INSTRUCCIÓN: Usa estos datos para personalizar tus respuestas. 
Cuando el usuario pregunte sobre su situación fiscal, IVA a pagar, gastos, 
deducciones o cualquier análisis financiero, usa ESTOS NÚMEROS REALES en lugar 
de ejemplos genéricos. Dirígete al usuario de forma personal ("en tu caso", 
"tus facturas muestran", "con tus ingresos de X€", etc.)
== FIN DATOS FINANCIEROS ==
"""
        return context.strip()

    except Exception as e:
        traceback.print_exc()
        return ""


@router.post("/")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        session_id = req.session_id or str(uuid.uuid4())

        # Get or create conversation
        conversation = None
        if req.conversation_id:
            result = await db.execute(
                select(Conversation).where(Conversation.id == req.conversation_id)
            )
            conversation = result.scalar_one_or_none()

        if not conversation:
            title = req.message[:60] if req.message else (req.file_name or "Documento adjunto")
            conversation = Conversation(
                session_id=session_id,
                user_id=req.user_id,
                title=title,
            )
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        # Load history
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        history = [{"role": m.role, "content": m.content} for m in messages]

        # Build financial context if user is logged in
        financial_context = ""
        if req.user_id:
            financial_context = await build_financial_context(req.user_id, db)

        # Handle image attachment
        image_b64 = None
        image_type = None
        if req.file_base64 and req.file_type and req.file_type.startswith("image/"):
            image_b64 = req.file_base64
            image_type = req.file_type

        # Call AI with financial context
        answer = await ask_ai(
            req.message,
            conversation_history=history,
            context=financial_context or None,
            image_base64=image_b64,
            image_media_type=image_type,
        )

        # Save messages
        user_msg_content = req.message
        if req.file_name:
            user_msg_content = f"[Archivo adjunto: {req.file_name}]\n{req.message}"

        db.add(Message(conversation_id=conversation.id, role="user", content=user_msg_content))
        db.add(Message(conversation_id=conversation.id, role="assistant", content=answer))
        await db.commit()

        return JSONResponse(content={
            "answer": answer,
            "conversation_id": conversation.id,
            "session_id": session_id,
        })

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": str(e), "type": type(e).__name__}
        )


@router.get("/conversations")
async def list_conversations(
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    if user_id:
        query = query.where(Conversation.user_id == user_id)
    elif session_id:
        query = query.where(Conversation.session_id == session_id)
    result = await db.execute(query.limit(50))
    convs = result.scalars().all()
    return [{"id": c.id, "title": c.title, "created_at": str(c.created_at), "updated_at": str(c.updated_at)} for c in convs]


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in messages]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if conv:
        await db.delete(conv)
        await db.commit()
    return {"ok": True}
