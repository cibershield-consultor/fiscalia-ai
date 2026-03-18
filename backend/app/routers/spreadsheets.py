"""
FiscalIA — Router de hojas de cálculo
Endpoints para leer, editar y generar Excel/CSV
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends
from typing import Optional
import io, json

from app.core.database import get_db
from app.models.invoice import Invoice
from app.services.spreadsheet_service import (
    parse_spreadsheet_for_ai,
    add_rows_to_excel,
    generate_invoice_report,
    generate_csv_export,
)
from app.services.ai_service import ask_ai

router = APIRouter()


# ── LEER y analizar con IA ─────────────────────────────────────
@router.post("/analyze")
async def analyze_spreadsheet(
    file: UploadFile = File(...),
    question: str = Form(default="Analiza este archivo y dame un resumen fiscal detallado"),
    user_id: Optional[int] = Form(default=None),
):
    """
    Upload an Excel or CSV file.
    The AI reads it and answers the user's question about it.
    """
    allowed = {"xlsx", "xls", "xlsm", "csv"}
    ext = file.filename.lower().split(".")[-1]
    if ext not in allowed:
        raise HTTPException(400, f"Formato no soportado. Usa: {', '.join(allowed)}")

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(400, "Archivo demasiado grande (máx. 10MB)")

    try:
        spreadsheet_text = parse_spreadsheet_for_ai(file_bytes, file.filename)
    except Exception as e:
        raise HTTPException(400, f"No se pudo leer el archivo: {str(e)}")

    prompt = f"""El usuario ha subido el archivo '{file.filename}' y pregunta: "{question}"

Aquí están los datos del archivo:

{spreadsheet_text}

Por favor:
1. Analiza los datos desde una perspectiva fiscal para autónomos españoles
2. Responde la pregunta del usuario usando los datos reales del archivo
3. Identifica: ingresos, gastos, IVA, deducciones posibles
4. Da recomendaciones fiscales concretas basadas en estos datos
5. Indica si hay datos que faltan o que podrían mejorarse"""

    answer = await ask_ai(prompt)

    return JSONResponse(content={
        "answer": answer,
        "file_summary": {
            "filename": file.filename,
            "size_kb": round(len(file_bytes) / 1024, 1),
            "preview": spreadsheet_text[:500] + "..." if len(spreadsheet_text) > 500 else spreadsheet_text,
        }
    })


# ── EDITAR Excel existente — añadir filas ─────────────────────
@router.post("/edit")
async def edit_spreadsheet(
    file: UploadFile = File(...),
    new_data: str = Form(...),  # JSON string with rows to add
):
    """
    Upload an Excel, add new rows (JSON), download the updated file.
    new_data: JSON array of objects matching the Excel column headers.
    Example: [{"Fecha":"01/01/2026","Concepto":"Factura","Importe":500}]
    """
    ext = file.filename.lower().split(".")[-1]
    if ext not in ("xlsx", "xls"):
        raise HTTPException(400, "Solo se pueden editar archivos .xlsx")

    file_bytes = await file.read()

    try:
        rows = json.loads(new_data)
        if not isinstance(rows, list):
            rows = [rows]
    except json.JSONDecodeError:
        raise HTTPException(400, "new_data debe ser un JSON válido")

    try:
        updated_bytes = add_rows_to_excel(file_bytes, rows)
    except Exception as e:
        raise HTTPException(500, f"Error al editar el archivo: {str(e)}")

    filename = file.filename.replace(".xlsx", "_editado.xlsx")
    return StreamingResponse(
        io.BytesIO(updated_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── GENERAR informe Excel desde facturas ──────────────────────
@router.get("/export/excel")
async def export_excel(
    año: int = Query(default=2026),
    user_id: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
):
    """Generate a complete Excel report with all invoices, fiscal summary and quarterly breakdown."""
    result = await db.execute(
        select(Invoice)
        .where(Invoice.user_id == user_id)
        .order_by(Invoice.fecha.asc())
    )
    invoices = result.scalars().all()

    # Filter by year
    invoices_year = [
        i for i in invoices
        if (getattr(i,'fecha',None) or getattr(i,'created_at',None)) and
           (getattr(i,'fecha',None) or getattr(i,'created_at',None)).year == año
    ]

    excel_bytes = generate_invoice_report(invoices_year, año)

    filename = f"FiscalIA_Facturas_{año}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── EXPORTAR CSV ──────────────────────────────────────────────
@router.get("/export/csv")
async def export_csv(
    año: int = Query(default=2026),
    user_id: int = Query(default=1),
    db: AsyncSession = Depends(get_db),
):
    """Export all invoices as CSV."""
    result = await db.execute(
        select(Invoice)
        .where(Invoice.user_id == user_id)
        .order_by(Invoice.fecha.asc())
    )
    invoices = result.scalars().all()

    invoices_year = [
        i for i in invoices
        if (getattr(i,'fecha',None) or getattr(i,'created_at',None)) and
           (getattr(i,'fecha',None) or getattr(i,'created_at',None)).year == año
    ]

    csv_bytes = generate_csv_export(invoices_year)

    filename = f"FiscalIA_Facturas_{año}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
