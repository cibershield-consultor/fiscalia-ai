from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
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
    # Check if trial/premium has expired
    plan = user.plan
    if user.plan_expires_at and datetime.utcnow() > user.plan_expires_at:
        plan = "free"

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "plan": plan,
            "plan_expires_at": str(user.plan_expires_at) if user.plan_expires_at else None,
            "avatar_initials": user.avatar_initials or (user.email[:2].upper()),
            "messages_today": user.messages_today or 0,
            "created_at": str(user.created_at),
        }
    }


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    # Generate initials
    initials = ""
    if req.full_name:
        parts = req.full_name.strip().split()
        initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else parts[0][1] if len(parts[0]) > 1 else '')).upper()
    if not initials:
        initials = req.email[:2].upper()

    # Free trial — new users get Premium free for FREE_TRIAL_DAYS
    trial_days = settings.FREE_TRIAL_DAYS
    trial_expires = datetime.utcnow() + timedelta(days=trial_days) if trial_days > 0 else None
    initial_plan = "premium" if trial_days > 0 else "free"

    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        avatar_initials=initials,
        plan=initial_plan,
        plan_expires_at=trial_expires,
        messages_today=0,
        messages_reset_at=datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    response = user_to_dict(user, token)

    # Add trial info to response
    if trial_days > 0:
        response["trial_message"] = f"🎉 ¡Bienvenido! Tienes {trial_days} días de Premium gratis para explorar todas las funciones."

    return JSONResponse(content=response)


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    # Auto-expire trial if needed
    if user.plan_expires_at and datetime.utcnow() > user.plan_expires_at and user.plan == "premium":
        user.plan = "free"
        user.plan_expires_at = None
        await db.commit()

    # Reset daily message counter if new day
    now = datetime.utcnow()
    if user.messages_reset_at and (now - user.messages_reset_at).days >= 1:
        user.messages_today = 0
        user.messages_reset_at = now
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return JSONResponse(content=user_to_dict(user, token))
