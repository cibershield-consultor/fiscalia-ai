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

# Herramienta de búsqueda web nativa de Groq
# La IA la usa automáticamente cuando necesita info más reciente que el contexto RAG
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Busca información actualizada en internet. Úsala cuando el contexto RAG "
            "no tenga datos suficientemente recientes sobre normativa fiscal española, "
            "cambios legislativos, nuevas resoluciones de la DGT, actualizaciones del BOE, "
            "o cualquier dato que pueda haber cambiado recientemente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Consulta de búsqueda en español, específica y concreta"
                }
            },
            "required": ["query"]
        }
    }
}

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
- Si la pregunta es sobre normativa reciente y el contexto no basta, usa web_search
  para buscar la información actualizada antes de responder.

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
    """Main chat function with RAG — retrieves context then generates response.
    Si la IA necesita info más reciente, usa web_search automáticamente."""
    import httpx
    from app.services.rag_service import retrieve_context, format_context_for_prompt

    # 3 fragmentos RAG (novedades del día tienen prioridad sobre base estática)
    rag_docs = await retrieve_context(question, n_results=3)
    rag_context, references = format_context_for_prompt(rag_docs)

    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n=== CONTEXTO OFICIAL ===\n{rag_context}\n=== FIN ==="

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

    # Primera llamada — con herramienta de web search disponible
    response = await client.chat.completions.create(
        model=MODEL_FAST,
        messages=messages,
        max_tokens=2000,
        temperature=0.45,
        tools=[WEB_SEARCH_TOOL],
        tool_choice="auto",
    )

    # Si la IA decide buscar en internet, ejecutar la búsqueda y volver a llamar
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tool_call = choice.message.tool_calls[0]
        search_query = json.loads(tool_call.function.arguments).get("query", question)

        # Ejecutar búsqueda web via DuckDuckGo (sin API key)
        web_result = await _web_search_duckduckgo(search_query)

        # Añadir resultado al hilo de mensajes y pedir respuesta final
        messages.append(choice.message)  # Mensaje del assistant con tool_call
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": web_result,
        })

        final_response = await client.chat.completions.create(
            model=MODEL_FAST,
            messages=messages,
            max_tokens=2000,
            temperature=0.45,
        )
        return final_response.choices[0].message.content

    return choice.message.content


async def _web_search_duckduckgo(query: str) -> str:
    """Búsqueda web via DuckDuckGo API (gratuita, sin API key).
    Devuelve un resumen de los primeros resultados relevantes."""
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as http:
            r = await http.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "FiscalIA/1.0"}
            )
            if r.status_code == 200:
                data = r.json()
                parts = []
                if data.get("AbstractText"):
                    parts.append(data["AbstractText"])
                    if data.get("AbstractURL"):
                        parts.append(f"Fuente: {data['AbstractURL']}")
                for topic in data.get("RelatedTopics", [])[:3]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        parts.append(topic["Text"])
                if parts:
                    return "\n".join(parts)
    except Exception:
        pass
    return f"No se encontraron resultados web para: {query}"




async def ask_ai_with_rag_stream(
    question: str,
    conversation_history: Optional[list] = None,
    financial_context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> AsyncIterator[str]:
    """Streaming RAG chat.
    Si la IA necesita buscar en internet, hace la búsqueda (no streaming) y luego
    hace la respuesta final en streaming."""
    from app.services.rag_service import retrieve_context, format_context_for_prompt

    # 3 fragmentos RAG (novedades del día tienen prioridad)
    rag_docs = await retrieve_context(question, n_results=3)
    rag_context, references = format_context_for_prompt(rag_docs)

    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n=== CONTEXTO OFICIAL ===\n{rag_context}\n=== FIN ==="

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

    # Primera llamada — no streaming, para detectar si la IA quiere buscar en internet
    probe = await client.chat.completions.create(
        model=MODEL_FAST,
        messages=messages,
        max_tokens=200,       # Solo para detectar tool_call, no para la respuesta
        temperature=0.45,
        tools=[WEB_SEARCH_TOOL],
        tool_choice="auto",
    )

    probe_choice = probe.choices[0]
    if probe_choice.finish_reason == "tool_calls" and probe_choice.message.tool_calls:
        # La IA quiere buscar — ejecutar búsqueda y añadir resultado
        tool_call = probe_choice.message.tool_calls[0]
        search_query = json.loads(tool_call.function.arguments).get("query", question)
        web_result = await _web_search_duckduckgo(search_query)

        messages.append(probe_choice.message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": web_result,
        })

    # Respuesta final en streaming (con o sin web search result en el contexto)
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
