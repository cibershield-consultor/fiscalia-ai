from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid
import traceback
from app.core.database import get_db
from app.models.conversation import Conversation, Message
from app.services.ai_service import ask_ai

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None


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
            conversation = Conversation(
                session_id=session_id,
                title=req.message[:60],
            )
            db.add(conversation)
            await db.commit()           # commit first so it gets an ID
            await db.refresh(conversation)

        # Load history
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()
        history = [{"role": m.role, "content": m.content} for m in messages]

        # Call OpenAI
        answer = await ask_ai(req.message, conversation_history=history)

        # Save messages
        db.add(Message(conversation_id=conversation.id, role="user",      content=req.message))
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


@router.get("/history/{conversation_id}")
async def get_history(conversation_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.content, "created_at": str(m.created_at)} for m in messages]
