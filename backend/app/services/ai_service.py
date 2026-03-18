"""
FiscalIA — Servicio IA optimizado
- Chat: llama-3.1-8b-instant (rápido)
- Clasificación/análisis: llama-3.3-70b-versatile (preciso)
"""
from groq import AsyncGroq
from typing import Optional, AsyncIterator
import json
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# Modelos
MODEL_FAST   = "llama-3.1-8b-instant"      # Chat — rápido, fluido
MODEL_SMART  = "llama-3.3-70b-versatile"   # Clasificación, análisis complejos

# ── System prompt del chat — conciso para reducir tokens ──────
SYSTEM_PROMPT = """Eres FiscalIA, asistente de fiscalidad y contabilidad española.

REGLAS CLAVE:
1. NO asumas el tipo de contribuyente (autónomo, empresa, asalariado...). Pregunta si es relevante.
2. Indica siempre que la normativa puede cambiar. Recomienda verificar en BOE, AEAT y TGSS.
3. No des asesoramiento vinculante. Recomienda gestor/asesor para decisiones importantes.
4. Clasifica gastos según PGC PYMEs (RD 1515/2007) cuando sea relevante.

CONOCIMIENTO (actualizado marzo 2026):
- IRPF 2026: 19%/24%/30%/37%/45%/47% (tramos estatales). Sumar tramo autonómico.
- IVA: 21% general, 10% reducido, 4% superreducido. M.303 trimestral.
- Autónomos: cotización por ingresos reales, 15 tramos (200€-590€/mes). Tarifa plana 80€ nuevos.
- VERIFACTU: Empresas (IS) desde 1/1/2027, autónomos (IRPF) desde 1/7/2027.
- CNAE-2025: Obligatorio actualizar desde 1/1/2026.
- RDL 16/2025 fue DEROGADO el 27/01/2026. Vigente RDL 2/2026 y RDL 3/2026.

REFERENCIAS OFICIALES (incluir siempre al menos una):
- AEAT IVA: https://sede.agenciatributaria.gob.es/Sede/iva.html
- AEAT IRPF: https://sede.agenciatributaria.gob.es/Sede/irpf.html
- AEAT Calendario: https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html
- AEAT Modelos: https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI01.shtml
- TGSS Autónomos: https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo
- BOE: https://www.boe.es/buscar/boe.php

FORMATO: Sé claro y conciso. Usa ## para secciones, bullets para listas. Termina con 1-2 referencias relevantes."""


async def ask_ai(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 1500,
    temperature: float = 0.5,
) -> str:
    """Non-streaming AI call. Uses fast model by default."""
    messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]

    if context:
        messages.append({"role": "system", "content": f"Datos del usuario:\n{context}"})
    if conversation_history:
        messages.extend(conversation_history[-10:])

    if image_base64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"}},
            {"type": "text", "text": question or "Analiza este documento."}
        ]
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model=model or MODEL_FAST,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content


async def ask_ai_stream(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> AsyncIterator[str]:
    """Streaming AI call — yields text chunks as they arrive."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        messages.append({"role": "system", "content": f"Datos del usuario:\n{context}"})
    if conversation_history:
        messages.extend(conversation_history[-10:])

    if image_base64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"}},
            {"type": "text", "text": question or "Analiza este documento."}
        ]
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})

    stream = await client.chat.completions.create(
        model=MODEL_FAST,
        messages=messages,
        max_tokens=1500,
        temperature=0.5,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def classify_expense(description: str, amount: float) -> dict:
    """Classify expense using smart model for accuracy."""
    prompt = f"""Clasifica este gasto/ingreso según PGC PYMEs español (RD 1515/2007).

Descripción: {description}
Importe: {amount}€

Responde SOLO con JSON válido:
{{
    "categoria": "suministros|material_oficina|software|formacion|marketing|transporte|dietas|seguros|asesoria|cuota_autonomo|alquiler|equipos|telefono|otros|servicios|productos",
    "cuenta_pgc": "número cuenta PGC (ej: 628)",
    "nombre_cuenta": "nombre de la cuenta",
    "deducible": true,
    "porcentaje_deduccion": 100,
    "explicacion": "por qué esta cuenta PGC",
    "condiciones_deduccion": "condiciones para deducir",
    "nota_contribuyente": "diferencias según tipo contribuyente"
}}"""

    response = await client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": "Experto en PGC PYMEs español. Responde SOLO JSON válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400, temperature=0.1,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        start = text.find("{"); end = text.rfind("}") + 1
        if start >= 0: text = text[start:end]
        return json.loads(text.strip())
    except Exception:
        return {
            "categoria": "otros", "cuenta_pgc": "629",
            "nombre_cuenta": "Otros servicios",
            "deducible": False, "porcentaje_deduccion": 0,
            "explicacion": "No se pudo clasificar",
            "condiciones_deduccion": "Consultar asesor",
            "nota_contribuyente": "Depende del tipo de contribuyente"
        }


async def generate_financial_insights(data: dict) -> list[str]:
    """Generate financial insights using fast model."""
    prompt = f"""Datos financieros: {data}

Genera 3-5 insights útiles y accionables en JSON array.
Ejemplo: ["Tu margen es 32%, por encima del 25% recomendado", "IVA a ingresar: 450€"]
Responde SOLO con el JSON array."""

    response = await client.chat.completions.create(
        model=MODEL_FAST,
        messages=[
            {"role": "system", "content": "Asesor financiero España. Responde SOLO JSON array válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400, temperature=0.4,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        start = text.find("["); end = text.rfind("]") + 1
        if start >= 0: text = text[start:end]
        return json.loads(text.strip())
    except Exception:
        return ["Añade más datos para obtener insights detallados."]


async def ask_ai_for_json(prompt: str, system: str = "") -> str:
    """
    Dedicated function for JSON generation tasks (Excel, classification).
    Uses smart model with strict JSON instructions. No fiscal system prompt.
    """
    response = await client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": system or "Responde SOLO con JSON válido, sin texto adicional, sin markdown."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=2000,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()
    # Clean any markdown
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            p = part.strip()
            if p.startswith("json"): p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                return p
    # Find JSON boundaries
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        s = raw.find(start_char)
        e = raw.rfind(end_char) + 1
        if s >= 0 and e > s:
            return raw[s:e]
    return raw
