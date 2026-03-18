from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid, traceback, base64
from datetime import datetime
from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.services.ai_service import ask_ai

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    user_id: Optional[int] = None
    # File attachment as base64
    file_base64: Optional[str] = None
    file_type: Optional[str] = None   # "image/jpeg", "image/png", "application/pdf"
    file_name: Optional[str] = None


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

        # Handle file — only pass to AI if it's an image (Groq supports vision)
        image_b64 = None
        image_type = None
        if req.file_base64 and req.file_type and req.file_type.startswith("image/"):
            image_b64 = req.file_base64
            image_type = req.file_type

        # Call AI
        answer = await ask_ai(
            req.message,
            conversation_history=history,
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
async def list_conversations(user_id: Optional[int] = None, session_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
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
