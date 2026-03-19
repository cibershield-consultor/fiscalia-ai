"""
FiscalIA — Security utilities
JWT, password hashing, input sanitization, rate limiting
"""
import re
import bleach
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from app.core.config import settings


# ── Password ──────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload["exp"] = expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except Exception:
        return None


# ── Input sanitization ────────────────────────────────────────

# Allowed tags for rich text fields (basically none — we want plain text)
_ALLOWED_TAGS: list = []
_ALLOWED_ATTRS: dict = {}

def sanitize_text(text: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Strip HTML/JS injection attempts and enforce length limits.
    Used on all user-supplied text before storing or passing to AI.
    """
    if text is None:
        return None
    # Strip HTML tags and entities
    cleaned = bleach.clean(str(text), tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
    # Remove null bytes and control characters (except newlines/tabs)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    # Enforce length
    return cleaned[:max_length].strip()


def sanitize_ai_input(text: Optional[str]) -> Optional[str]:
    """
    Sanitize text before sending to AI — prevents prompt injection.
    Removes common injection patterns.
    """
    if text is None:
        return None
    cleaned = sanitize_text(text, max_length=4000)
    if cleaned is None:
        return None
    # Remove common prompt injection attempts
    injection_patterns = [
        r'ignore previous instructions',
        r'ignore all instructions',
        r'disregard your instructions',
        r'you are now',
        r'act as',
        r'pretend you are',
        r'jailbreak',
        r'<\|.*?\|>',         # LLM special tokens
        r'\[INST\]',
        r'\[/INST\]',
        r'<<SYS>>',
        r'<</SYS>>',
    ]
    for pattern in injection_patterns:
        cleaned = re.sub(pattern, '[input filtrado]', cleaned, flags=re.IGNORECASE)
    return cleaned


def is_safe_email(email: str) -> bool:
    """Basic email validation."""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= 254


def is_strong_password(password: str) -> tuple[bool, str]:
    """Check password strength. Returns (is_valid, error_message)."""
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres"
    if len(password) > 128:
        return False, "La contraseña no puede superar los 128 caracteres"
    return True, ""
