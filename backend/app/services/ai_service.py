"""
FiscalIA — Servicio IA con RAG integrado
Estrategia de tokens:
  MODEL_FAST  (8B)  — 30.000 TPM gratuitos → todo el chat conversacional
  MODEL_SMART (70B) —  6.000 TPM gratuitos → solo classify/JSON (pocas llamadas, alta precisión)
  System prompt compacto (~300 tokens vs ~800 originales)
  Historial recortado a 4 mensajes (mayor ahorro por conversación)
  RAG reducido a 3 fragmentos
  max_tokens output: 2000 chat, 500 classify, 350 insights, 3000 JSON/Excel
"""
from groq import AsyncGroq
from typing import Optional, AsyncIterator
import json
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# 8B: ~30.000 TPM gratuitos — para todo el chat conversacional
MODEL_FAST  = "llama-3.1-8b-instant"
# 70B: ~6.000 TPM gratuitos — solo tareas de precisión (classify, JSON, Excel)
MODEL_SMART = "llama-3.3-70b-versatile"

# Prompt compacto con instrucción de web search y prioridad a novedades recientes
SYSTEM_PROMPT_BASE = """Eres FiscalIA, experto en fiscalidad, contabilidad y finanzas españolas.

REGLAS:
- Nunca asumas el tipo de contribuyente (autónomo/empresa/asalariado); pregunta si es relevante.
- Basa las respuestas en el contexto oficial proporcionado. Cita las fuentes.
- Si no tienes la info, indícalo y dirige a la fuente oficial.
- No des asesoramiento vinculante; recomienda gestor/asesor para decisiones importantes.
- Advierte de verificar en BOE/AEAT/TGSS, pues la normativa cambia.
- Clasifica gastos según PGC PYMEs (RD 1515/2007) cuando corresponda.
- Si el contexto contiene entradas marcadas "⚡ ACTUALIZACIÓN RECIENTE", dales MÁXIMA PRIORIDAD:
  son novedades del día descargadas de fuentes oficiales y prevalecen sobre datos previos.

ESTILO:
- Respuestas completas con contexto, matices y casos especiales.
- Ejemplos numéricos concretos cuando ayuden (ej: "40.000€ facturados → 420€/mes de cuota").
- Usa ## y listas para temas con varios puntos; ## Resumen al final en temas complejos.
- Explica el significado práctico de cifras. Indica variaciones por perfil de contribuyente.
- Termina con 1-2 URLs oficiales. Añade disclaimer en decisiones económicas importantes.

FUENTES (URL completa al citar):
BOE boe.es | AEAT sede.agenciatributaria.gob.es | TGSS sede.seg-social.gob.es
DGT hacienda.gob.es | ICAC icac.gob.es | SEPE sepe.es
LGSS BOE-A-2015-11724 | LGT BOE-A-2003-23186 | LETA BOE-A-2007-13409
País Vasco y Navarra: régimen foral propio.

CON CONTEXTO RAG: úsalo como base principal, amplía con práctica, señala contradicciones."""


async def ask_ai_with_rag(
    question: str,
    conversation_history: Optional[list] = None,
    financial_context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> str:
    """Main chat function con RAG + web search automático en backend."""
    import httpx
    from app.services.rag_service import retrieve_context, format_context_for_prompt

    # 1. Recuperar contexto RAG (base estática + novedades del día)
    rag_docs = await retrieve_context(question, n_results=3)
    rag_context, references = format_context_for_prompt(rag_docs)

    # 2. Datos en tiempo real de fuentes oficiales según el tema de la pregunta
    #    (seg-social.es para jubilación, agenciatributaria.gob.es para IRPF/IVA, etc.)
    live_context = await _get_live_context(question)

    # 3. Construir system prompt
    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n=== CONTEXTO BASE ===\n{rag_context}\n=== FIN ==="
    if live_context:
        system += f"\n\n=== ⚡ DATOS OFICIALES EN TIEMPO REAL (prevalecen sobre cualquier otro dato) ===\n{live_context}\n=== FIN ==="

    messages = [{"role": "system", "content": system}]
    if financial_context:
        messages.append({"role": "system", "content": f"Datos financieros:\n{financial_context}"})
    if conversation_history:
        messages.extend(conversation_history[-4:])

    if image_base64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"}},
            {"type": "text", "text": question or "Analiza este documento fiscal."}
        ]
    else:
        user_content = question
    messages.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model=MODEL_FAST,
        messages=messages,
        max_tokens=2000,
        temperature=0.45,
    )
    return response.choices[0].message.content


async def _get_live_context(question: str) -> str:
    """
    Obtiene datos en tiempo real de fuentes oficiales según el tema de la pregunta.
    Usa live_data_service que raspa directamente seg-social.es, agenciatributaria.gob.es, etc.
    Falla silenciosamente — si no hay datos frescos, la IA usa solo el RAG estático.
    """
    try:
        from app.services.live_data_service import get_live_data_for_question
        return await get_live_data_for_question(question)
    except Exception:
        return ""






async def ask_ai_with_rag_stream(
    question: str,
    conversation_history: Optional[list] = None,
    financial_context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> AsyncIterator[str]:
    """Streaming RAG chat con web search en backend (sin depender de tool use del modelo)."""
    from app.services.rag_service import retrieve_context, format_context_for_prompt

    # 1. RAG: novedades del día + base estática
    rag_docs = await retrieve_context(question, n_results=3)
    rag_context, references = format_context_for_prompt(rag_docs)

    # 2. Datos en tiempo real de fuentes oficiales (misma lógica que versión no-streaming)
    live_context = await _get_live_context(question)

    # 3. Construir mensajes
    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n=== CONTEXTO BASE ===\n{rag_context}\n=== FIN ==="
    if live_context:
        system += f"\n\n=== ⚡ DATOS OFICIALES EN TIEMPO REAL (prevalecen sobre cualquier otro dato) ===\n{live_context}\n=== FIN ==="

    messages = [{"role": "system", "content": system}]
    if financial_context:
        messages.append({"role": "system", "content": f"Datos del usuario:\n{financial_context}"})
    if conversation_history:
        messages.extend(conversation_history[-4:])
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
        max_tokens=2000,
        temperature=0.45,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# Keep backward-compatible names
async def ask_ai(question, conversation_history=None, context=None,
                 image_base64=None, image_media_type=None, **kwargs) -> str:
    return await ask_ai_with_rag(question, conversation_history, context, image_base64, image_media_type)

async def ask_ai_stream(question, conversation_history=None, context=None,
                        image_base64=None, image_media_type=None):
    async for chunk in ask_ai_with_rag_stream(question, conversation_history, context, image_base64, image_media_type):
        yield chunk


async def classify_expense(description: str, amount: float) -> dict:
    """Classify expense using smart model with detailed explanation."""
    prompt = f"""Clasifica este gasto/ingreso según el PGC PYMEs español (RD 1515/2007).

Descripción: {description}
Importe: {amount}€

Responde SOLO con JSON válido:
{{
  "categoria": "suministros|material_oficina|software|formacion|marketing|transporte|dietas|seguros|asesoria|cuota_autonomo|alquiler|equipos|telefono|otros|servicios|productos",
  "cuenta_pgc": "número cuenta (ej: 628)",
  "nombre_cuenta": "nombre completo de la cuenta PGC",
  "deducible": true,
  "porcentaje_deduccion": 100,
  "resumen_ia": "1-2 frases explicando: qué tipo de gasto/ingreso es, en qué cuenta PGC va y por qué es o no deducible. Menciona si varía según el tipo de contribuyente.",
  "condiciones_deduccion": "condiciones concretas para que sea deducible",
  "nota_contribuyente": "diferencias clave según sea autónomo, empresa o asalariado"
}}"""

    response = await client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": "Eres experto en PGC PYMEs y fiscalidad española. Responde SOLO con JSON válido, sin texto adicional."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500, temperature=0.1,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        s = text.find("{"); e = text.rfind("}") + 1
        if s >= 0: text = text[s:e]
        return json.loads(text)
    except Exception:
        return {
            "categoria": "otros", "cuenta_pgc": "629", "nombre_cuenta": "Otros servicios",
            "deducible": False, "porcentaje_deduccion": 0,
            "resumen_ia": "No se pudo clasificar automáticamente. Revisa manualmente la categoría.",
            "condiciones_deduccion": "Consultar con asesor fiscal",
            "nota_contribuyente": "La deducibilidad depende del tipo de contribuyente"
        }


async def generate_financial_insights(data: dict) -> list[str]:
    prompt = f"Datos: {data}\nGenera 3-4 insights financieros útiles. Solo JSON array de strings."
    response = await client.chat.completions.create(
        model=MODEL_FAST,
        messages=[{"role":"system","content":"Asesor financiero. Solo JSON array."},
                  {"role":"user","content":prompt}],
        max_tokens=350, temperature=0.4,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text: text = text.split("```")[1]; text = text[4:] if text.startswith("json") else text
        s = text.find("["); e = text.rfind("]") + 1
        if s >= 0: text = text[s:e]
        return json.loads(text)
    except Exception:
        return ["Añade más datos para obtener insights detallados."]


async def ask_ai_for_json(prompt: str, system: str = "") -> str:
    """For Excel generation — smart model, JSON only."""
    response = await client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": system or "Solo JSON válido, sin markdown."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=3000, temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            p = part.strip()
            if p.startswith("json"): p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                return p
    for sc, ec in [("{", "}"), ("[", "]")]:
        s = raw.find(sc); e = raw.rfind(ec) + 1
        if s >= 0 and e > s: return raw[s:e]
    return raw
