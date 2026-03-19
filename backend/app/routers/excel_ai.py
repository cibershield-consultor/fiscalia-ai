"""
FiscalIA — Router IA Excel
Endpoints dedicados para la IA especializada en hojas de cálculo.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import io

from app.services.excel_ai_service import process_excel_request, chat_with_excel_ai

router = APIRouter()


class ExcelChatRequest(BaseModel):
    message: str
    conversation_history: Optional[list] = None


@router.post("/chat")
async def excel_ai_chat(req: ExcelChatRequest):
    """Conversational AI about Excel — answers questions and plans spreadsheets."""
    answer = await chat_with_excel_ai(req.message, req.conversation_history)
    return JSONResponse(content={"answer": answer})


@router.post("/generate")
async def excel_ai_generate(
    request: str = Form(...),
    file: Optional[UploadFile] = File(default=None),
):
    """
    Generate or modify an Excel file using AI.
    - request: natural language description of what to create/add
    - file: optional existing Excel to modify
    """
    if not request.strip():
        raise HTTPException(400, "Describe qué quieres que la IA cree en el Excel.")

    file_bytes = None
    filename = None
    if file and file.filename:
        ext = file.filename.lower().split(".")[-1]
        if ext not in ("xlsx", "xls", "csv"):
            raise HTTPException(400, "Solo se aceptan archivos .xlsx, .xls o .csv")
        file_bytes = await file.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(400, "Archivo demasiado grande (máx. 10MB)")
        filename = file.filename

    try:
        excel_bytes, sheet_name, explanation = await process_excel_request(
            request, file_bytes, filename
        )
    except Exception as e:
        raise HTTPException(500, f"Error al generar el Excel: {str(e)}")

    base_name = filename.replace(".xlsx","").replace(".xls","") if filename else "FiscalIA"
    output_name = f"{base_name}_+{sheet_name[:20]}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{output_name}"',
            "X-Sheet-Name": sheet_name,
            "X-Explanation": explanation,
        }
    )
