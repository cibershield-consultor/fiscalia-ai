"""Schemas Pydantic para facturas."""
from pydantic import BaseModel, field_validator
from typing import Optional


class InvoiceCreateRequest(BaseModel):
    tipo: str = "gasto"
    emisor: str = ""
    concepto: str = ""
    base_imponible: float = 0.0
    tipo_iva: float = 21.0
    fecha: Optional[str] = None
    user_id: Optional[int] = None
    categoria_pgc: Optional[str] = None
    deducible_override: Optional[str] = None
    porcentaje_override: Optional[float] = None
    notas: Optional[str] = None

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, v: str) -> str:
        allowed = {"gasto", "ingreso"}
        if v not in allowed:
            raise ValueError(f"tipo debe ser uno de: {allowed}")
        return v

    @field_validator("base_imponible")
    @classmethod
    def validate_importe(cls, v: float) -> float:
        if v < 0:
            raise ValueError("El importe no puede ser negativo")
        if v > 10_000_000:
            raise ValueError("Importe demasiado alto")
        return round(v, 2)

    @field_validator("tipo_iva")
    @classmethod
    def validate_iva(cls, v: float) -> float:
        allowed = {0.0, 4.0, 5.0, 10.0, 21.0}
        if v not in allowed:
            raise ValueError(f"Tipo IVA debe ser uno de: {allowed}")
        return v

    @field_validator("emisor", "concepto")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return v.strip()[:200] if v else v
