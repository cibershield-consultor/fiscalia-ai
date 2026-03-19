from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import jwt

from app.core.database import get_db
from app.core.logging_config import log
from app.core.security import sanitize_text, is_safe_email, is_strong_password
from app.core.rate_limit import limiter, AUTH_LIMIT
from fastapi import Request
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from app.models.user import User

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordConfirmRequest(BaseModel):
    token: str
    new_password: str


# ── Helpers ────────────────────────────────────────────────────
def get_initials(full_name: Optional[str], email: str) -> str:
    if full_name:
        parts = full_name.strip().split()
        return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else (parts[0][1] if len(parts[0]) > 1 else ''))).upper()
    return email[:2].upper()


def user_to_dict(user: User, token: str) -> dict:
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
            "avatar_initials": user.avatar_initials or get_initials(user.full_name, user.email),
            "messages_today": user.messages_today or 0,
            "created_at": str(user.created_at),
        }
    }


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency — extracts user from Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticación requerido")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub", 0))
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


# ── Register ───────────────────────────────────────────────────
@router.post("/register")
@limiter.limit(AUTH_LIMIT)
async def register(request: Request, req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Validate email and password
    if not is_safe_email(req.email):
        raise HTTPException(400, "Formato de email inválido")
    valid_pass, pass_err = is_strong_password(req.password)
    if not valid_pass:
        raise HTTPException(400, pass_err)
    if req.full_name:
        req.full_name = sanitize_text(req.full_name, max_length=100)

    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    trial_days = settings.FREE_TRIAL_DAYS
    trial_expires = datetime.utcnow() + timedelta(days=trial_days) if trial_days > 0 else None
    initial_plan = "premium" if trial_days > 0 else "free"

    user = User(
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name,
        avatar_initials=get_initials(req.full_name, req.email),
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
    if trial_days > 0:
        response["trial_message"] = f"🎉 ¡Bienvenido! Tienes {trial_days} días de Premium gratis."
    log.info(f"New user registered: {req.email}")
    return JSONResponse(content=response)


# ── Login ──────────────────────────────────────────────────────
@router.post("/login")
@limiter.limit(AUTH_LIMIT)
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")

    # Auto-expire trial
    if user.plan_expires_at and datetime.utcnow() > user.plan_expires_at and user.plan == "premium":
        user.plan = "free"
        user.plan_expires_at = None

    # Reset daily counter
    now = datetime.utcnow()
    if user.messages_reset_at and (now - user.messages_reset_at).days >= 1:
        user.messages_today = 0
        user.messages_reset_at = now

    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return JSONResponse(content=user_to_dict(user, token))


# ── Get current user ───────────────────────────────────────────
@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    plan = current_user.plan
    if current_user.plan_expires_at and datetime.utcnow() > current_user.plan_expires_at:
        plan = "free"
    return JSONResponse(content={
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "plan": plan,
        "plan_expires_at": str(current_user.plan_expires_at) if current_user.plan_expires_at else None,
        "avatar_initials": current_user.avatar_initials or get_initials(current_user.full_name, current_user.email),
        "messages_today": current_user.messages_today or 0,
        "created_at": str(current_user.created_at),
    })


# ── Update profile ─────────────────────────────────────────────
@router.put("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.email and req.email != current_user.email:
        existing = await db.execute(select(User).where(User.email == req.email))
        if existing.scalar_one_or_none():
            raise HTTPException(400, "Ese email ya está en uso por otra cuenta")
        current_user.email = req.email

    if req.full_name is not None:
        current_user.full_name = req.full_name
        current_user.avatar_initials = get_initials(req.full_name, current_user.email)

    await db.commit()
    await db.refresh(current_user)

    return JSONResponse(content={
        "ok": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "avatar_initials": current_user.avatar_initials,
            "plan": current_user.plan,
        }
    })


# ── Change password ────────────────────────────────────────────
@router.put("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(400, "La contraseña actual es incorrecta")
    if len(req.new_password) < 6:
        raise HTTPException(400, "La nueva contraseña debe tener al menos 6 caracteres")

    current_user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return JSONResponse(content={"ok": True, "message": "Contraseña actualizada correctamente"})


# ── Reset password (forgot password) ──────────────────────────
@router.post("/reset-password/request")
async def request_password_reset(
    req: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a reset token valid for 1 hour.
    In production: send this token via email.
    For now: returns the token directly (dev mode).
    """
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    # Always return 200 to avoid email enumeration
    if not user:
        return JSONResponse(content={"ok": True, "message": "Si el email existe, recibirás instrucciones."})

    # Create a short-lived reset token
    reset_token = create_access_token(
        {"sub": str(user.id), "purpose": "reset"},
        expires_delta=timedelta(hours=1)
    )

    # TODO in production: send email with reset link
    # For now return token directly so user can use it
    return JSONResponse(content={
        "ok": True,
        "message": "Token de recuperación generado.",
        "reset_token": reset_token,  # Remove this in production, send via email instead
        "note": "En producción este token se enviaría por email. Úsalo en /auth/reset-password/confirm"
    })


@router.post("/reset-password/confirm")
async def confirm_password_reset(
    req: ResetPasswordConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply new password using the reset token."""
    try:
        payload = jwt.decode(req.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "reset":
            raise HTTPException(400, "Token inválido")
        user_id = int(payload.get("sub", 0))
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "El token ha expirado. Solicita uno nuevo.")
    except Exception:
        raise HTTPException(400, "Token inválido")

    if len(req.new_password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    return JSONResponse(content={"ok": True, "message": "Contraseña restablecida correctamente. Ya puedes iniciar sesión."})


# ── Delete account ─────────────────────────────────────────────
@router.delete("/account")
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.delete(current_user)
    await db.commit()
    return JSONResponse(content={"ok": True, "message": "Cuenta eliminada correctamente"})
