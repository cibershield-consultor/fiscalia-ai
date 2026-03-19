"""
FiscalIA — Servicio IA con RAG integrado
Modelo rápido (8B) + contexto vectorial + web en tiempo real
"""
from groq import AsyncGroq
from typing import Optional, AsyncIterator
import json
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

MODEL_FAST  = "llama-3.1-8b-instant"
MODEL_SMART = "llama-3.3-70b-versatile"

SYSTEM_PROMPT_BASE = """Eres FiscalIA, asistente especializado en fiscalidad, contabilidad y asesoramiento financiero español.

REGLAS FUNDAMENTALES:
1. NUNCA asumas el tipo de contribuyente. No sabes si es autónomo, empresa, asalariado u otro perfil. Pregunta si es relevante para la respuesta.
2. Basa tus respuestas en las FUENTES OFICIALES proporcionadas en el contexto. Cita siempre las fuentes.
3. Si el contexto no tiene la información, indícalo claramente y dirige a la fuente oficial.
4. No des asesoramiento vinculante. Recomienda gestor/asesor para decisiones importantes.
5. La normativa cambia frecuentemente. Indica siempre que el usuario verifique en BOE, AEAT y TGSS.
6. Clasifica gastos según PGC PYMEs (RD 1515/2007) cuando sea relevante.

ESTILO DE RESPUESTA — MUY IMPORTANTE:
- Sé detallado y completo. No respondas con una sola frase cuando el tema lo requiere.
- Explica el contexto, los matices y los casos especiales relevantes para que el usuario entienda bien.
- Si hay condiciones, excepciones o variaciones importantes, menciónalas explícitamente.
- Usa ejemplos numéricos concretos cuando ayuden a entender (ej: "si facturas 40.000€ anuales, tu cuota de autónomo sería de 420€/mes según el tramo 10").
- Para temas con varios puntos, usa ## para secciones y listas con guiones para mayor claridad.
- En temas fiscales complejos, incluye al final un bloque "## Resumen" con los puntos clave.
- Cuando des cifras o porcentajes, explica también qué significan en la práctica.
- Si la respuesta varía según el tipo de contribuyente, explica cómo afecta a cada perfil.
- Termina siempre con 1-2 referencias oficiales relevantes con sus URLs completas.
- Incluye una nota de disclaimer cuando el tema requiera decisiones económicas importantes.

CUANDO TENGAS CONTEXTO DE FUENTES OFICIALES:
- Usa esa información como base principal de tu respuesta
- Amplía con explicaciones prácticas sobre cómo aplicar esa normativa
- Si hay información contradictoria, indica cuál es la más reciente y por qué"""


async def ask_ai_with_rag(
    question: str,
    conversation_history: Optional[list] = None,
    financial_context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> str:
    """Main chat function with RAG — retrieves context then generates response."""
    from app.services.rag_service import retrieve_context, format_context_for_prompt

    # Retrieve relevant context
    rag_docs = await retrieve_context(question, n_results=4)
    rag_context, references = format_context_for_prompt(rag_docs)

    # Build system prompt with RAG context
    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n=== CONOCIMIENTO RECUPERADO DE FUENTES OFICIALES ===\n{rag_context}\n=== FIN DEL CONTEXTO ==="

    messages = [{"role": "system", "content": system}]

    if financial_context:
        messages.append({"role": "system", "content": f"Datos financieros del usuario:\n{financial_context}"})

    if conversation_history:
        messages.extend(conversation_history[-8:])

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
        max_tokens=2200,
        temperature=0.45,
    )
    return response.choices[0].message.content


async def ask_ai_with_rag_stream(
    question: str,
    conversation_history: Optional[list] = None,
    financial_context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> AsyncIterator[str]:
    """Streaming RAG chat — yields text chunks as they arrive."""
    from app.services.rag_service import retrieve_context, format_context_for_prompt

    # Retrieve relevant context
    rag_docs = await retrieve_context(question, n_results=4)
    rag_context, references = format_context_for_prompt(rag_docs)

    system = SYSTEM_PROMPT_BASE
    if rag_context:
        system += f"\n\n=== CONOCIMIENTO RECUPERADO DE FUENTES OFICIALES ===\n{rag_context}\n=== FIN DEL CONTEXTO ==="

    messages = [{"role": "system", "content": system}]
    if financial_context:
        messages.append({"role": "system", "content": f"Datos del usuario:\n{financial_context}"})
    if conversation_history:
        messages.extend(conversation_history[-8:])
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
        max_tokens=2200,
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
        max_tokens=2000, temperature=0.2,
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
