from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.models.invoice import Transaction
from app.services.ai_service import generate_financial_insights

router = APIRouter()


class TransactionCreate(BaseModel):
    tipo: str  # "ingreso" | "gasto"
    concepto: str
    importe: float
    categoria: Optional[str] = None
    fecha: Optional[datetime] = None
    deducible: bool = False
    notas: Optional[str] = None
    session_id: Optional[str] = None


def get_trimestre(fecha: datetime) -> int:
    return (fecha.month - 1) // 3 + 1


@router.post("/transactions")
async def add_transaction(req: TransactionCreate, db: AsyncSession = Depends(get_db)):
    fecha = req.fecha or datetime.utcnow()
    tx = Transaction(
        user_id=1,  # TODO: get from auth token
        tipo=req.tipo,
        concepto=req.concepto,
        importe=req.importe,
        categoria=req.categoria,
        fecha=fecha,
        trimestre=get_trimestre(fecha),
        año=fecha.year,
        deducible=req.deducible,
        notas=req.notas,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    return tx


@router.get("/summary")
async def get_summary(
    año: int = Query(default=datetime.utcnow().year),
    trimestre: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Transaction).where(Transaction.año == año, Transaction.user_id == 1)
    if trimestre:
        query = query.where(Transaction.trimestre == trimestre)

    result = await db.execute(query)
    transactions = result.scalars().all()

    ingresos = sum(t.importe for t in transactions if t.tipo == "ingreso")
    gastos = sum(t.importe for t in transactions if t.tipo == "gasto")
    gastos_deducibles = sum(t.importe for t in transactions if t.tipo == "gasto" and t.deducible)
    beneficio = ingresos - gastos
    margen = (beneficio / ingresos * 100) if ingresos > 0 else 0

    # Tax estimations
    iva_repercutido = ingresos * 0.21
    iva_soportado = sum(t.importe * 0.21 for t in transactions if t.tipo == "gasto" and t.deducible)
    iva_a_pagar = max(0, iva_repercutido - iva_soportado)

    irpf_retenido = ingresos * 0.15
    base_irpf = ingresos - gastos_deducibles
    irpf_estimado = calcular_irpf(base_irpf)

    # Categories breakdown
    categorias: dict = {}
    for t in transactions:
        cat = t.categoria or "sin_categoria"
        if cat not in categorias:
            categorias[cat] = {"ingresos": 0, "gastos": 0}
        if t.tipo == "ingreso":
            categorias[cat]["ingresos"] += t.importe
        else:
            categorias[cat]["gastos"] += t.importe

    # Monthly breakdown
    meses: dict = {}
    for t in transactions:
        mes = t.fecha.strftime("%Y-%m") if t.fecha else "desconocido"
        if mes not in meses:
            meses[mes] = {"ingresos": 0, "gastos": 0}
        if t.tipo == "ingreso":
            meses[mes]["ingresos"] += t.importe
        else:
            meses[mes]["gastos"] += t.importe

    financial_data = {
        "ingresos": ingresos,
        "gastos": gastos,
        "beneficio": beneficio,
        "margen_pct": round(margen, 2),
        "gastos_deducibles": gastos_deducibles,
        "iva_a_pagar": round(iva_a_pagar, 2),
        "irpf_estimado": round(irpf_estimado, 2),
        "irpf_retenido": round(irpf_retenido, 2),
        "diferencia_irpf": round(irpf_estimado - irpf_retenido, 2),
        "num_transacciones": len(transactions),
        "año": año,
        "trimestre": trimestre,
    }

    insights = await generate_financial_insights(financial_data)

    return {
        **financial_data,
        "categorias": categorias,
        "meses": meses,
        "insights": insights,
    }


@router.get("/transactions")
async def list_transactions(
    año: Optional[int] = Query(default=None),
    trimestre: Optional[int] = Query(default=None),
    tipo: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Transaction).where(Transaction.user_id == 1).order_by(Transaction.fecha.desc())
    if año:
        query = query.where(Transaction.año == año)
    if trimestre:
        query = query.where(Transaction.trimestre == trimestre)
    if tipo:
        query = query.where(Transaction.tipo == tipo)

    result = await db.execute(query)
    transactions = result.scalars().all()
    return transactions


def calcular_irpf(base: float) -> float:
    """Calculate estimated IRPF based on 2024 tax brackets."""
    if base <= 0:
        return 0.0

    tramos = [
        (12450, 0.19),
        (7750, 0.24),   # 20200 - 12450
        (15000, 0.30),  # 35200 - 20200
        (24800, 0.37),  # 60000 - 35200
        (240000, 0.45), # 300000 - 60000
    ]

    impuesto = 0.0
    restante = base

    for limite, tipo in tramos:
        if restante <= 0:
            break
        gravable = min(restante, limite)
        impuesto += gravable * tipo
        restante -= gravable

    if restante > 0:
        impuesto += restante * 0.47

    return impuesto
