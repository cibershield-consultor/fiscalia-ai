from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    numero = Column(String, nullable=True)
    tipo = Column(String, default="gasto")  # "ingreso" | "gasto"
    emisor = Column(String, nullable=True)
    receptor = Column(String, nullable=True)
    fecha = Column(DateTime, nullable=True)
    base_imponible = Column(Float, default=0.0)
    tipo_iva = Column(Float, default=21.0)
    cuota_iva = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    concepto = Column(Text, nullable=True)
    categoria = Column(String, nullable=True)
    deducible = Column(Boolean, default=True)
    porcentaje_deduccion = Column(Float, default=100.0)
    archivo_path = Column(String, nullable=True)
    ocr_texto = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="invoices")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tipo = Column(String, nullable=False)  # "ingreso" | "gasto"
    concepto = Column(String, nullable=False)
    importe = Column(Float, nullable=False)
    categoria = Column(String, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)
    trimestre = Column(Integer, nullable=True)  # 1, 2, 3, 4
    año = Column(Integer, nullable=True)
    deducible = Column(Boolean, default=False)
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
