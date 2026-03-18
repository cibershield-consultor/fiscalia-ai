from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.models.invoice import Invoice, Transaction
from app.services.ai_service import generate_financial_insights

router = APIRouter()


def get_trimestre(fecha: datetime) -> int:
    return (fecha.month - 1) // 3 + 1


def calcular_irpf(base: float) -> float:
    if base <= 0: return 0.0
    tramos = [(12450,.19),(7750,.24),(15000,.30),(24800,.37),(240000,.45)]
    imp, rest = 0.0, base
    for lim, tipo in tramos:
        if rest <= 0: break
        g = min(rest, lim); imp += g * tipo; rest -= g
    if rest > 0: imp += rest * 0.47
    return round(imp, 2)


@router.get("/summary")
async def get_summary(
    año: int = Query(default=datetime.utcnow().year),
    trimestre: Optional[int] = Query(default=None),
    user_id: int = Query(default=1),  # REQUIRED for user isolation
    db: AsyncSession = Depends(get_db),
):
    # CRITICAL: filter by user_id
    result = await db.execute(select(Invoice).where(Invoice.user_id == user_id))
    all_invoices = result.scalars().all()

    invoices = []
    for inv in all_invoices:
        ref = inv.fecha or inv.created_at
        if not ref: continue
        if ref.year != año: continue
        if trimestre and get_trimestre(ref) != trimestre: continue
        invoices.append(inv)

    ingresos = sum(i.base_imponible for i in invoices if i.tipo == "ingreso")
    gastos = sum(i.base_imponible for i in invoices if i.tipo == "gasto")
    gastos_deducibles = sum(
        i.base_imponible * (i.porcentaje_deduccion / 100)
        for i in invoices if i.tipo == "gasto" and i.deducible
    )
    beneficio = ingresos - gastos
    margen = (beneficio / ingresos * 100) if ingresos > 0 else 0

    iva_repercutido = sum(i.cuota_iva for i in invoices if i.tipo == "ingreso")
    iva_soportado = sum(
        i.cuota_iva * (i.porcentaje_deduccion / 100)
        for i in invoices if i.tipo == "gasto" and i.deducible
    )
    iva_a_pagar = max(0, iva_repercutido - iva_soportado)
    irpf_retenido = ingresos * 0.15
    base_irpf = ingresos - gastos_deducibles
    irpf_estimado = calcular_irpf(base_irpf)

    categorias: dict = {}
    for inv in invoices:
        cat = inv.categoria or "sin_categoria"
        if cat not in categorias:
            categorias[cat] = {"ingresos": 0.0, "gastos": 0.0}
        if inv.tipo == "ingreso": categorias[cat]["ingresos"] += inv.base_imponible
        else: categorias[cat]["gastos"] += inv.base_imponible

    meses: dict = {}
    for inv in invoices:
        ref = inv.fecha or inv.created_at
        mes = ref.strftime("%Y-%m") if ref else "sin-fecha"
        if mes not in meses: meses[mes] = {"ingresos": 0.0, "gastos": 0.0}
        if inv.tipo == "ingreso": meses[mes]["ingresos"] += inv.base_imponible
        else: meses[mes]["gastos"] += inv.base_imponible

    financial_data = {
        "ingresos": round(ingresos, 2), "gastos": round(gastos, 2),
        "beneficio": round(beneficio, 2), "margen_pct": round(margen, 2),
        "gastos_deducibles": round(gastos_deducibles, 2),
        "iva_repercutido": round(iva_repercutido, 2),
        "iva_soportado": round(iva_soportado, 2),
        "iva_a_pagar": round(iva_a_pagar, 2),
        "irpf_estimado": round(irpf_estimado, 2),
        "irpf_retenido": round(irpf_retenido, 2),
        "diferencia_irpf": round(irpf_estimado - irpf_retenido, 2),
        "num_transacciones": len(invoices), "año": año, "trimestre": trimestre,
    }

    insights = await generate_financial_insights(financial_data)
    return {**financial_data, "categorias": categorias, "meses": meses, "insights": insights}


class TransactionCreate(BaseModel):
    tipo: str
    concepto: str
    importe: float
    categoria: Optional[str] = None
    fecha: Optional[datetime] = None
    deducible: bool = False
    notas: Optional[str] = None
    user_id: Optional[int] = 1


@router.post("/transactions")
async def add_transaction(req: TransactionCreate, db: AsyncSession = Depends(get_db)):
    fecha = req.fecha or datetime.utcnow()
    cuota_iva = req.importe * 0.21
    invoice = Invoice(
        user_id=req.user_id or 1,
        tipo=req.tipo, concepto=req.concepto,
        emisor="Manual", base_imponible=req.importe,
        tipo_iva=21.0, cuota_iva=round(cuota_iva,2),
        total=round(req.importe+cuota_iva,2),
        fecha=fecha, categoria=req.categoria,
        deducible=req.deducible,
        porcentaje_deduccion=100.0 if req.deducible else 0.0,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.get("/transactions")
async def list_transactions(
    año: Optional[int] = Query(default=None),
    trimestre: Optional[int] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    user_id: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
):
    # CRITICAL: filter by user_id
    query = select(Invoice).where(Invoice.user_id == user_id).order_by(Invoice.created_at.desc())
    if tipo: query = query.where(Invoice.tipo == tipo)
    result = await db.execute(query)
    invoices = result.scalars().all()
    out = []
    for inv in invoices:
        ref = inv.fecha or inv.created_at
        if año and ref and ref.year != año: continue
        if trimestre and ref and get_trimestre(ref) != trimestre: continue
        out.append(inv)
    return out
