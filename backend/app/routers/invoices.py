from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
import os, uuid, traceback

from app.core.database import get_db
from app.core.logging_config import log
from app.core.security import sanitize_text
from app.core.rate_limit import limiter, INVOICE_LIMIT
from fastapi import Request
from app.models.invoice import Invoice
from app.services.ai_service import classify_expense

router = APIRouter()

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Plan General Contable PYMEs — grupos y cuentas
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

OPCIONES_DEDUCCION = {
    "100": "100% deducible",
    "50":  "50% deducible (uso mixto)",
    "30":  "30% deducible (proporcional vivienda)",
    "0":   "No deducible",
    "custom": "Porcentaje personalizado",
}


@router.post("/")
@limiter.limit(INVOICE_LIMIT)
async def create_invoice(
    request: Request,
    tipo: str = Form(default="gasto"),
    emisor: str = Form(default=""),
    concepto: str = Form(default=""),
    base_imponible: float = Form(default=0.0),
    tipo_iva: float = Form(default=21.0),
    fecha: Optional[str] = Form(default=None),
    # New fields
    categoria_pgc: Optional[str] = Form(default=None),
    deducible_override: Optional[str] = Form(default=None),   # "100","50","30","0","custom"
    porcentaje_override: Optional[float] = Form(default=None), # used when deducible_override="custom"
    notas: Optional[str] = Form(default=None),
    archivo: Optional[UploadFile] = File(default=None),
    db: AsyncSession = Depends(get_db),
):
    archivo_path = None
    if archivo and archivo.filename:
        ext = os.path.splitext(archivo.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        archivo_path = os.path.join(UPLOAD_DIR, filename)
        with open(archivo_path, "wb") as f:
            content = await archivo.read()
            f.write(content)

    # Sanitize text inputs
    emisor   = sanitize_text(emisor,   max_length=200) or ""
    concepto = sanitize_text(concepto, max_length=500) or ""
    notas    = sanitize_text(notas,    max_length=1000)

    cuota_iva = base_imponible * (tipo_iva / 100)
    total = base_imponible + cuota_iva

    # AI classification
    classification = await classify_expense(concepto or emisor, base_imponible)

    # Allow manual override of deductibility
    if deducible_override is not None:
        if deducible_override == "100":
            deducible = True
            porcentaje_deduccion = 100.0
        elif deducible_override == "0":
            deducible = False
            porcentaje_deduccion = 0.0
        elif deducible_override == "custom" and porcentaje_override is not None:
            deducible = porcentaje_override > 0
            porcentaje_deduccion = porcentaje_override
        else:
            try:
                pct = float(deducible_override)
                deducible = pct > 0
                porcentaje_deduccion = pct
            except (ValueError, TypeError):
                deducible = classification.get("deducible", False)
                porcentaje_deduccion = classification.get("porcentaje_deduccion", 0)
    else:
        deducible = classification.get("deducible", False)
        porcentaje_deduccion = classification.get("porcentaje_deduccion", 0)

    # PGC category — use provided or map from AI category
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
        user_id=1,  # Fixed below via user_id form field
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
    categoria_pgc: Optional[str] = Form(default=None),
    deducible: Optional[bool] = Form(default=None),
    porcentaje_deduccion: Optional[float] = Form(default=None),
    notas: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Update editable fields: PGC category, deductibility, notes."""
    result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Factura no encontrada")

    if categoria_pgc is not None:
        invoice.categoria = categoria_pgc
    if deducible is not None:
        invoice.deducible = deducible
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
    # CRITICAL: always filter by user_id to prevent data leakage
    uid = user_id or 1
    query = select(Invoice).where(Invoice.user_id == uid).order_by(Invoice.created_at.desc())
    if tipo:
        query = query.where(Invoice.tipo == tipo)
    result = await db.execute(query)
    invoices = result.scalars().all()
    return [_invoice_to_dict(i) for i in invoices]


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: int,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    uid = user_id or 1
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == uid)
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
        "suministros":    "628",
        "software":       "629",
        "formacion":      "629",
        "marketing":      "627",
        "transporte":     "624",
        "dietas":         "629",
        "seguros":        "625",
        "asesoria":       "623",
        "cuota_autonomo": "642",
        "alquiler":       "621",
        "equipos":        "681",
        "telefono":       "628",
        "material_oficina": "629",
        "servicios":      "705",
        "productos":      "700",
    }
    return mapping.get(ai_cat, "629")
