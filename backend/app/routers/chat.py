from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid, traceback, json
from datetime import datetime
from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.models.invoice import Invoice
from app.models.user import User
from app.services.ai_service import ask_ai, ask_ai_stream


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for i, page in enumerate(reader.pages[:20]):  # Max 20 pages
            text = page.extract_text()
            if text and text.strip():
                text_parts.append(f"--- Página {i+1} ---\n{text.strip()}")
        if not text_parts:
            return "[PDF sin texto extraíble — puede ser un PDF escaneado o de imagen]"
        full_text = "\n\n".join(text_parts)
        # Limit to ~8000 chars to avoid token overflow
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "\n\n[... texto truncado por longitud ...]"
        return full_text
    except Exception as e:
        return f"[Error al leer PDF: {str(e)}]" 

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    user_id: Optional[int] = None
    # Multiple file support
    files: Optional[list[dict]] = None  # [{base64, type, name}, ...]
    # Keep single file for backwards compat
    file_base64: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    stream: bool = False


async def build_financial_context(user_id: int, db: AsyncSession) -> str:
    try:
        result = await db.execute(
            select(Invoice).where(Invoice.user_id == user_id).order_by(Invoice.fecha.desc())
        )
        invoices = result.scalars().all()
        if not invoices: return ""

        año = datetime.utcnow().year
        this_year = [i for i in invoices if (i.fecha or i.created_at) and (i.fecha or i.created_at).year == año]

        ingresos = sum(i.base_imponible for i in this_year if i.tipo == "ingreso")
        gastos = sum(i.base_imponible for i in this_year if i.tipo == "gasto")
        gas_ded = sum(i.base_imponible*(i.porcentaje_deduccion/100) for i in this_year if i.tipo=="gasto" and i.deducible)
        iva_rep = sum(i.cuota_iva for i in this_year if i.tipo=="ingreso")
        iva_sop = sum(i.cuota_iva*(i.porcentaje_deduccion/100) for i in this_year if i.tipo=="gasto" and i.deducible)
        beneficio = ingresos - gastos

        cats: dict = {}
        for inv in this_year:
            cat = inv.categoria or "otros"
            cats[cat] = cats.get(cat, 0) + inv.base_imponible

        top_cats = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:5]
        recent = invoices[:5]
        recent_lines = "\n".join([
            f"  - {inv.tipo.upper()} | {inv.emisor or inv.concepto or 'Sin desc'} | "
            f"{inv.base_imponible:.2f}€ | {inv.categoria or 'sin cat'} | "
            f"{'deducible '+str(inv.porcentaje_deduccion)+'%' if inv.deducible else 'no deducible'}"
            for inv in recent
        ])

        user_res = await db.execute(select(User).where(User.id == user_id))
        user = user_res.scalar_one_or_none()
        plan = user.plan if user else "free"

        return f"""== DATOS FINANCIEROS DEL USUARIO (año {año}) ==
Ingresos: {ingresos:.2f}€ | Gastos: {gastos:.2f}€ | Beneficio: {beneficio:.2f}€
Gastos deducibles: {gas_ded:.2f}€ | IVA repercutido: {iva_rep:.2f}€ | IVA soportado: {iva_sop:.2f}€
IVA a ingresar estimado: {max(0,iva_rep-iva_sop):.2f}€ | Total facturas año: {len(this_year)} | Plan: {plan}

Categorías principales: {', '.join(f'{c}:{a:.0f}€' for c,a in top_cats)}

Últimas facturas:
{recent_lines}

INSTRUCCIÓN: Usa estos datos para personalizar respuestas. Habla en primera persona al usuario ("tus facturas muestran..."). Pero NO asumas el tipo de contribuyente si no lo ha indicado.
== FIN DATOS =="""
    except Exception:
        traceback.print_exc()
        return ""


@router.post("/")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        session_id = req.session_id or str(uuid.uuid4())

        # Get or create conversation
        conversation = None
        if req.conversation_id:
            result = await db.execute(select(Conversation).where(Conversation.id == req.conversation_id))
            conversation = result.scalar_one_or_none()

        if not conversation:
            title = req.message[:60] if req.message else "Documento adjunto"
            conversation = Conversation(session_id=session_id, user_id=req.user_id, title=title)
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)

        # Load history
        result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)
        )
        history = [{"role": m.role, "content": m.content} for m in result.scalars().all()]

        # Financial context (only for logged in users)
        financial_context = ""
        if req.user_id:
            financial_context = await build_financial_context(req.user_id, db)

        # Handle files — support multiple, including PDFs
        files = req.files or []
        # Backwards compat: single file
        if req.file_base64 and req.file_type:
            files.append({"base64": req.file_base64, "type": req.file_type, "name": req.file_name or "archivo"})

        image_b64, image_type = None, None
        pdf_texts = []
        file_descriptions = []

        for f in files:
            ftype = f.get("type", "")
            fname = f.get("name", "archivo")
            file_descriptions.append(fname)

            if ftype.startswith("image/") and not image_b64:
                # Use first image for vision
                image_b64 = f["base64"]
                image_type = ftype

            elif ftype == "application/pdf" or fname.lower().endswith(".pdf"):
                # Extract PDF text
                import base64 as b64lib
                try:
                    pdf_bytes = b64lib.b64decode(f["base64"])
                    pdf_text = extract_pdf_text(pdf_bytes)
                    pdf_texts.append(f"=== Contenido del PDF: {fname} ===\n{pdf_text}\n=== Fin del PDF ===")
                except Exception as e:
                    pdf_texts.append(f"[Error procesando {fname}: {str(e)}]")

        # Build message content
        message_text = req.message
        if file_descriptions:
            message_text = f"[Archivos adjuntos: {', '.join(file_descriptions)}]\n{req.message}"

        # STREAMING response
        if req.stream:
            async def generate():
                full_answer = ""
                try:
                    async for chunk in ask_ai_stream(
                        question_with_pdfs,
                        conversation_history=history,
                        context=financial_context or None,
                        image_base64=image_b64,
                        image_media_type=image_type,
                    ):
                        full_answer += chunk
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                    # Save to DB after streaming completes
                    db.add(Message(conversation_id=conversation.id, role="user", content=message_text))
                    db.add(Message(conversation_id=conversation.id, role="assistant", content=full_answer))
                    await db.commit()

                    yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id, 'session_id': session_id})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return StreamingResponse(generate(), media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

        # NON-STREAMING response
        answer = await ask_ai(
            question_with_pdfs,
            conversation_history=history,
            context=financial_context or None,
            image_base64=image_b64,
            image_media_type=image_type,
        )

        db.add(Message(conversation_id=conversation.id, role="user", content=message_text))
        db.add(Message(conversation_id=conversation.id, role="assistant", content=answer))
        await db.commit()

        return JSONResponse(content={"answer": answer, "conversation_id": conversation.id, "session_id": session_id})

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": str(e), "type": type(e).__name__})


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
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in result.scalars().all()]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if conv:
        await db.delete(conv)
        await db.commit()
    return {"ok": True}
