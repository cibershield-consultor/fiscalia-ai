from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid
from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.services.ai_service import ask_ai

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    session_id: str


@router.post("/", response_model=ChatResponse)
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    # Get or create session
    session_id = req.session_id or str(uuid.uuid4())

    # Get or create conversation
    if req.conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == req.conversation_id))
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversación no encontrada")
    else:
        conversation = Conversation(
            session_id=session_id,
            title=req.message[:60] + "..." if len(req.message) > 60 else req.message,
        )
        db.add(conversation)
        await db.flush()

    # Get conversation history
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    history = [{"role": m.role, "content": m.content} for m in messages]

    # Get AI response
    answer = await ask_ai(req.message, conversation_history=history)

    # Save messages
    user_msg = Message(conversation_id=conversation.id, role="user", content=req.message)
    ai_msg = Message(conversation_id=conversation.id, role="assistant", content=answer)
    db.add(user_msg)
    db.add(ai_msg)
    await db.commit()
    await db.refresh(conversation)

    return ChatResponse(answer=answer, conversation_id=conversation.id, session_id=session_id)


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in messages]
