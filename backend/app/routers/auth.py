from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import User

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def user_to_dict(user: User, token: str) -> dict:
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "plan": user.plan,
            "avatar_initials": user.avatar_initials or (user.full_name[:2].upper() if user.full_name else user.email[:2].upper()),
            "messages_today": user.messages_today,
            "created_at": str(user.created_at),
        }
    }


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    initials = ""
    if req.full_name:
        parts = req.full_name.strip().split()
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else parts[0][1])).upper()
    else:
        initials = req.email[:2].upper()

    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        avatar_initials=initials,
        plan="free",
        messages_today=0,
        messages_reset_at=datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return JSONResponse(content=user_to_dict(user, token))


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    token = create_access_token({"sub": str(user.id)})
    return JSONResponse(content=user_to_dict(user, token))


@router.get("/me")
async def get_me(db: AsyncSession = Depends(get_db)):
    # Simple endpoint — auth via token handled in router
    return {"status": "ok"}
