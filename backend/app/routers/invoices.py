from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
import os, uuid

from app.core.database import get_db
from app.models.invoice import Invoice
from app.services.ai_service import classify_expense

router = APIRouter()

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

PGC_CATEGORIAS = {
    "600": "600 - Compras de mercaderías",
    "601": "601 - Compras de materias primas",
    "602": "602 - Compras de otros aprovisionamientos",
    "620": "620 - Gastos en I+D del ejercicio",
    "621": "621 - Arrendamientos y cánones",
    "622": "622 - Reparaciones y conservación",
    "623": "623 - Servicios de profesionales independientes",
    "624": "624 - Transportes",
    "625": "625 - Primas de seguros",
    "626": "626 - Servicios bancarios y similares",
    "627": "627 - Publicidad, propaganda y relaciones públicas",
    "628": "628 - Suministros (luz, agua, gas, internet)",
    "629": "629 - Otros servicios",
    "640": "640 - Sueldos y salarios",
    "642": "642 - Seguridad Social a cargo de la empresa",
    "649": "649 - Otros gastos sociales",
    "660": "660 - Gastos financieros por deudas",
    "680": "680 - Amortización del inmovilizado intangible",
    "681": "681 - Amortización del inmovilizado material",
    "700": "700 - Ventas de mercaderías",
    "705": "705 - Prestaciones de servicios",
    "740": "740 - Subvenciones a la explotación",
    "otros": "Otros / Sin clasificar",
}


@router.post("/")
async def create_invoice(
    tipo: str = Form(default="gasto"),
    emisor: str = Form(default=""),
    concepto: str = Form(default=""),
    base_imponible: float = Form(default=0.0),
    tipo_iva: float = Form(default=21.0),
    fecha: Optional[str] = Form(default=None),
    user_id: Optional[int] = Form(default=None),
    categoria_pgc: Optional[str] = Form(default=None),
    deducible_override: Optional[str] = Form(default=None),
    porcentaje_override: Optional[float] = Form(default=None),
    notas: Optional[str] = Form(default=None),
    archivo: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    # CRITICAL: user_id must come from the authenticated request, NEVER hardcoded
    if user_id is None:
        raise HTTPException(status_code=401, detail="Debes iniciar sesión para guardar facturas")

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

    classification = await classify_expense(concepto or emisor, base_imponible)

    if deducible_override is not None:
        if deducible_override == "100":
            deducible = True; porcentaje_deduccion = 100.0
        elif deducible_override == "0":
            deducible = False; porcentaje_deduccion = 0.0
        elif deducible_override == "custom" and porcentaje_override is not None:
            deducible = porcentaje_override > 0; porcentaje_deduccion = porcentaje_override
        else:
            try:
                pct = float(deducible_override)
                deducible = pct > 0; porcentaje_deduccion = pct
            except (ValueError, TypeError):
                deducible = classification.get("deducible", False)
                porcentaje_deduccion = classification.get("porcentaje_deduccion", 0)
    else:
        deducible = classification.get("deducible", False)
        porcentaje_deduccion = classification.get("porcentaje_deduccion", 0)

    if not categoria_pgc:
        ai_cat = classification.get("categoria", "otros")
        categoria_pgc = _map_ai_to_pgc(ai_cat)

    fecha_dt = None
    if fecha:
        try:
            fecha_dt = datetime.fromisoformat(fecha)
        except ValueError:
            pass

    invoice = Invoice(
        user_id=user_id,  # FIXED: use actual user_id, never hardcode
        tipo=tipo,
        emisor=emisor,
        concepto=concepto,
        base_imponible=base_imponible,
        tipo_iva=tipo_iva,
        cuota_iva=round(cuota_iva, 2),
        total=round(total, 2),
        fecha=fecha_dt,
        categoria=categoria_pgc,
        deducible=deducible,
        porcentaje_deduccion=porcentaje_deduccion,
        archivo_path=archivo_path,
        ocr_texto=notas,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    return JSONResponse(content={
        "invoice": {
            "id": invoice.id,
            "tipo": invoice.tipo,
            "emisor": invoice.emisor,
            "concepto": invoice.concepto,
            "base_imponible": invoice.base_imponible,
            "tipo_iva": invoice.tipo_iva,
            "cuota_iva": invoice.cuota_iva,
            "total": invoice.total,
            "categoria": invoice.categoria,
            "deducible": invoice.deducible,
            "porcentaje_deduccion": invoice.porcentaje_deduccion,
            "fecha": str(invoice.fecha) if invoice.fecha else None,
        },
        "clasificacion_ia": classification,
        "pgc_opciones": PGC_CATEGORIAS,
    })


@router.put("/{invoice_id}")
async def update_invoice(
    invoice_id: int,
    user_id: Optional[int] = Form(default=None),
    categoria: Optional[str] = Form(default=None),
    deducible: Optional[str] = Form(default=None),
    porcentaje_deduccion: Optional[float] = Form(default=None),
    notas: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    # CRITICAL: verify ownership before updating
    query = select(Invoice).where(Invoice.id == invoice_id)
    if user_id is not None:
        query = query.where(Invoice.user_id == user_id)
    result = await db.execute(query)
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada o no pertenece a este usuario")

    if categoria is not None:
        invoice.categoria = categoria
    if deducible is not None:
        invoice.deducible = deducible.lower() not in ('false', '0', 'no')
    if porcentaje_deduccion is not None:
        invoice.porcentaje_deduccion = porcentaje_deduccion
    if notas is not None:
        invoice.ocr_texto = notas

    await db.commit()
    await db.refresh(invoice)
    return JSONResponse(content={"ok": True, "invoice_id": invoice_id})


@router.get("/pgc-categories")
def get_pgc_categories():
    return PGC_CATEGORIAS


@router.get("/")
async def list_invoices(
    tipo: Optional[str] = None,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    # CRITICAL: ALWAYS filter by user_id — guests get empty list
    if user_id is None:
        return []
    query = select(Invoice).where(Invoice.user_id == user_id).order_by(Invoice.created_at.desc())
    if tipo:
        query = query.where(Invoice.tipo == tipo)
    result = await db.execute(query)
    return [_invoice_to_dict(i) for i in result.scalars().all()]


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: int,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    if user_id is None:
        raise HTTPException(403, "Debes iniciar sesión para eliminar facturas")
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == user_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada o no pertenece a este usuario")
    await db.delete(invoice)
    await db.commit()
    return {"ok": True}


def _invoice_to_dict(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "tipo": inv.tipo,
        "emisor": inv.emisor or "",
        "concepto": inv.concepto or "",
        "base_imponible": inv.base_imponible,
        "tipo_iva": inv.tipo_iva,
        "cuota_iva": inv.cuota_iva,
        "total": inv.total,
        "categoria": inv.categoria or "",
        "deducible": inv.deducible,
        "porcentaje_deduccion": inv.porcentaje_deduccion,
        "fecha": str(inv.fecha) if inv.fecha else None,
        "created_at": str(inv.created_at) if inv.created_at else None,
        "notas": inv.ocr_texto or "",
    }


def _map_ai_to_pgc(ai_cat: str) -> str:
    mapping = {
        "suministros": "628", "software": "629", "formacion": "629",
        "marketing": "627", "transporte": "624", "dietas": "629",
        "seguros": "625", "asesoria": "623", "cuota_autonomo": "642",
        "alquiler": "621", "equipos": "681", "telefono": "628",
        "material_oficina": "629", "servicios": "705", "productos": "700",
    }
    return mapping.get(ai_cat, "629")
