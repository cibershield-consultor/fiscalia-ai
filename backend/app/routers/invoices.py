from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
import os
import uuid
from app.core.database import get_db
from app.models.invoice import Invoice
from app.services.ai_service import classify_expense

router = APIRouter()

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/")
async def create_invoice(
    tipo: str = Form(default="gasto"),
    emisor: str = Form(default=""),
    concepto: str = Form(default=""),
    base_imponible: float = Form(default=0.0),
    tipo_iva: float = Form(default=21.0),
    fecha: Optional[str] = Form(default=None),
    archivo: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Save file if provided
    archivo_path = None
    if archivo and archivo.filename:
        ext = os.path.splitext(archivo.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        archivo_path = os.path.join(UPLOAD_DIR, filename)
        with open(archivo_path, "wb") as f:
            content = await archivo.read()
            f.write(content)

    cuota_iva = base_imponible * (tipo_iva / 100)
    total = base_imponible + cuota_iva

    # AI classification
    classification = await classify_expense(concepto or emisor, base_imponible)

    fecha_dt = None
    if fecha:
        try:
            fecha_dt = datetime.fromisoformat(fecha)
        except ValueError:
            pass

    invoice = Invoice(
        user_id=1,  # TODO: from auth
        tipo=tipo,
        emisor=emisor,
        concepto=concepto,
        base_imponible=base_imponible,
        tipo_iva=tipo_iva,
        cuota_iva=round(cuota_iva, 2),
        total=round(total, 2),
        fecha=fecha_dt,
        categoria=classification.get("categoria"),
        deducible=classification.get("deducible", False),
        porcentaje_deduccion=classification.get("porcentaje_deduccion", 0),
        archivo_path=archivo_path,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    return {
        "invoice": invoice,
        "clasificacion_ia": classification,
    }


@router.get("/")
async def list_invoices(
    tipo: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Invoice).where(Invoice.user_id == 1).order_by(Invoice.created_at.desc())
    if tipo:
        query = query.where(Invoice.tipo == tipo)
    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    await db.delete(invoice)
    await db.commit()
    return {"message": "Factura eliminada"}
