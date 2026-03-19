"""Schemas Pydantic para el chat."""
from pydantic import BaseModel, field_validator
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[int] = None
    user_id: Optional[int] = None
    files: Optional[list[dict]] = None
    file_base64: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    stream: bool = False

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El mensaje no puede estar vacío")
        if len(v) > 8000:
            raise ValueError("El mensaje es demasiado largo (máx. 8000 caracteres)")
        return v


class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    session_id: str
