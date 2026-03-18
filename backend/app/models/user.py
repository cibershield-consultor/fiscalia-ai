from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class PlanType(str, enum.Enum):
    FREE = "free"
    PREMIUM = "premium"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    nif = Column(String, nullable=True)
    actividad = Column(String, nullable=True)
    regimen = Column(String, default="estimacion_directa")
    plan = Column(String, default=PlanType.FREE)
    plan_expires_at = Column(DateTime, nullable=True)
    messages_today = Column(Integer, default=0)
    messages_reset_at = Column(DateTime, default=datetime.utcnow)
    stripe_customer_id = Column(String, nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    avatar_initials = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user", lazy="dynamic")
    invoices = relationship("Invoice", back_populates="user", lazy="dynamic")
    transactions = relationship("Transaction", back_populates="user", lazy="dynamic")
