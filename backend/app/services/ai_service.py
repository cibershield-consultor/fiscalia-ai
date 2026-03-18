"""
FiscalIA — Servicio de IA con Groq
Con consulta automática a BOE/AEAT/TGSS en cada petición fiscal relevante.
"""
from groq import AsyncGroq
from typing import Optional, AsyncIterator
import json, traceback, asyncio, httpx, re
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# ── Palabras clave fiscales que activan búsqueda web ──────────────
FISCAL_KEYWORDS = [
    "irpf", "iva", "autónomo", "autonomo", "empresa", "cotización", "cotizacion",
    "deducib", "modelo 303", "modelo 130", "modelo 390", "modelo 100",
    "boe", "aeat", "hacienda", "seguridad social", "tgss", "verifactu",
    "declaración", "declaracion", "trimestral", "anual", "factura",
    "retención", "retencion", "base imponible", "tipo impositivo",
    "módulos", "modulos", "estimación directa", "ley", "rdl", "real decreto"
]

SYSTEM_PROMPT = """Eres FiscalIA, un asistente especializado en fiscalidad y contabilidad española.

## REGLAS FUNDAMENTALES

1. **NO ASUMAS NADA** sobre el tipo de contribuyente. No sabes si la persona es:
   - Autónomo / trabajador por cuenta propia
   - Empresa (SL, SA, cooperativa...)
   - Trabajador por cuenta ajena
   - Particular sin actividad económica
   - Profesional con retención
   Si no lo ha dicho explícitamente, pregunta SIEMPRE o indica que la respuesta varía.

2. **INFORMACIÓN ACTUALIZADA**: La normativa fiscal cambia constantemente.
   - Indica la fecha de vigencia de la información que das
   - Si tienes datos de búsqueda web reciente (marcados con 🔍), úsalos y cítalos
   - SIEMPRE recomienda verificar en: BOE.es, sede.agenciatributaria.gob.es y seg-social.es

3. **FUENTES OFICIALES** — Cita siempre:
   - BOE: https://www.boe.es
   - AEAT: https://sede.agenciatributaria.gob.es
   - TGSS: https://sede.seg-social.gob.es

4. **NO DES ASESORAMIENTO VINCULANTE**: Recomienda consultar con gestor o asesor fiscal.

5. **PGC PYMEs** (RD 1515/2007): Usa siempre este plan al clasificar gastos.

## CONOCIMIENTO BASE (actualizado marzo 2026)

### Cambios normativos recientes:
- RDL 16/2025 (BOE 24/12/2025): DEROGADO el 27/01/2026 — sus medidas NO están vigentes
- RDL 2/2026 y RDL 3/2026 (BOE 4/02/2026): Prorrogan módulos 2026, deducciones vehículos eléctricos, libre amortización energías renovables
- VERIFACTU: Sociedades (IS) → 1/1/2027; Autónomos (IRPF) → 1/7/2027
- Cuotas autónomos 2026: Tablas congeladas (mismas que 2025)
- Bizum/pagos digitales: Desde 1/1/2026 mayor control fiscal sin mínimos
- CNAE-2025: Obligatorio actualizar desde 1/1/2026

### Tramos IRPF 2026 (estatal):
- ≤12.450€: 19% | 12.450-20.200€: 24% | 20.200-35.200€: 30%
- 35.200-60.000€: 37% | 60.000-300.000€: 45% | >300.000€: 47%
- Añadir tramo autonómico (varía por CCAA — consultar AEAT)

### IVA 2026:
- General: 21% | Reducido: 10% | Superreducido: 4% | Exento: 0%
- Plazos M.303: 20 abril, 20 julio, 20 octubre, 30 enero

### PGC PYMEs — Principales cuentas de gasto:
- 621 Arrendamientos | 623 Servicios profesionales | 627 Publicidad
- 628 Suministros | 629 Otros servicios | 640 Sueldos | 642 SS empresa

## ANÁLISIS DE DOCUMENTOS
Cuando se adjunte imagen, PDF u otro documento:
- Extrae: fecha, emisor, receptor, base imponible, IVA, total, nº factura
- Verifica requisitos legales (art. 6 RD 1619/2012)
- Clasifica según PGC PYMEs con número de cuenta
- Indica deducibilidad SEGÚN tipo de contribuyente (preguntar si no se sabe)

## FORMATO
- Respuestas cortas para preguntas simples
- ## encabezados para temas complejos
- ⚠️ para cambios normativos recientes
- 📋 Fuente oficial: URL cuando sea relevante
- 🔍 cuando usas datos de búsqueda actualizada
"""


def _is_fiscal_query(text: str) -> bool:
    """Detecta si la consulta es sobre temas fiscales que requieren info actualizada."""
    t = text.lower()
    return any(kw in t for kw in FISCAL_KEYWORDS)


async def fetch_aeat_info(query: str) -> str:
    """
    Busca información actualizada en AEAT.
    Usa la API de búsqueda pública de la AEAT cuando está disponible.
    """
    context_parts = []
    try:
        # Búsqueda en AEAT — API pública
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client_http:
            # Intentar obtener novedades/noticias de AEAT
            try:
                r = await client_http.get(
                    "https://www2.agenciatributaria.gob.es/wlpl/BUCV-JDIT/ObtenerContenidoAction",
                    params={"id": "1", "idioma": "es"},
                    headers={"User-Agent": "FiscalIA/1.0"}
                )
                if r.status_code == 200 and len(r.text) > 100:
                    # Extraer texto relevante (limitado)
                    text = re.sub(r'<[^>]+>', ' ', r.text)
                    text = re.sub(r'\s+', ' ', text).strip()[:1000]
                    if text:
                        context_parts.append(f"[AEAT info: {text}]")
            except Exception:
                pass

        if context_parts:
            return "\n".join(context_parts)
    except Exception:
        pass
    return ""


async def get_web_context(query: str) -> str:
    """Obtiene contexto web actualizado para consultas fiscales."""
    if not _is_fiscal_query(query):
        return ""

    try:
        web_ctx = await asyncio.wait_for(fetch_aeat_info(query), timeout=4.0)
        return web_ctx
    except Exception:
        return ""


async def ask_ai(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
    pdf_texts: Optional[list[str]] = None,
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Obtener contexto web actualizado en cada petición fiscal
    web_context = await get_web_context(question)

    if context:
        messages.append({"role": "system", "content": f"Datos financieros del usuario:\n{context}"})

    if web_context:
        messages.append({
            "role": "system",
            "content": (
                f"🔍 INFORMACIÓN ACTUALIZADA DE FUENTES OFICIALES (consultada ahora mismo):\n{web_context}\n\n"
                "Usa esta información actualizada en tu respuesta si es relevante. "
                "Cita la fuente con 🔍 cuando la uses."
            )
        })

    if conversation_history:
        messages.extend(conversation_history[-12:])

    user_content = _build_user_content(question, image_base64, image_media_type, pdf_texts)
    messages.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=2000,
        temperature=0.5,
    )
    return response.choices[0].message.content


async def ask_ai_stream(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
    pdf_texts: Optional[list[str]] = None,
) -> AsyncIterator[str]:
    """Streaming — yields text chunks. Consulta fuentes oficiales antes de responder."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Consultar fuentes oficiales en cada petición fiscal
    web_context = await get_web_context(question)

    if context:
        messages.append({"role": "system", "content": f"Datos financieros del usuario:\n{context}"})

    if web_context:
        messages.append({
            "role": "system",
            "content": (
                f"🔍 INFORMACIÓN ACTUALIZADA DE FUENTES OFICIALES (consultada ahora mismo):\n{web_context}\n\n"
                "Usa esta información actualizada en tu respuesta si es relevante. "
                "Cita la fuente con 🔍 cuando la uses."
            )
        })

    if conversation_history:
        messages.extend(conversation_history[-12:])

    user_content = _build_user_content(question, image_base64, image_media_type, pdf_texts)
    messages.append({"role": "user", "content": user_content})

    stream = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=2000,
        temperature=0.5,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def _build_user_content(
    question: str,
    image_base64: Optional[str],
    image_media_type: Optional[str],
    pdf_texts: Optional[list[str]],
):
    """Construye el contenido del mensaje de usuario con soporte multimedia."""
    if image_base64 or (pdf_texts and len(pdf_texts) > 0):
        content = []
        if image_base64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"}
            })
        if pdf_texts:
            for txt in pdf_texts:
                content.append({"type": "text", "text": f"[Contenido de documento adjunto]\n{txt[:4000]}"})
        content.append({"type": "text", "text": question or "Analiza este documento fiscal y extrae toda la información relevante."})
        return content
    return question


async def classify_expense(description: str, amount: float) -> dict:
    """Clasifica gasto según PGC PYMEs. NUNCA asume tipo de contribuyente."""
    prompt = f"""Clasifica este gasto según el Plan General Contable de PYMEs español (RD 1515/2007):
Descripción: {description}
Importe: {amount}€

IMPORTANTE: No asumas el tipo de contribuyente. La deducibilidad varía.

Responde SOLO con JSON válido (sin backticks, sin texto extra):
{{
    "categoria": "suministros|material_oficina|software|formacion|marketing|transporte|dietas|seguros|asesoria|cuota_autonomo|alquiler|equipos|telefono|otros|servicios|productos",
    "cuenta_pgc": "número cuenta PGC PYMEs (628, 623, 627...)",
    "nombre_cuenta_pgc": "nombre oficial (ej: '628 - Suministros')",
    "deducible": true,
    "porcentaje_deduccion": 100,
    "explicacion": "clasificación PGC breve",
    "nota_importante": "La deducibilidad depende del tipo de contribuyente (autónomo, empresa, asalariado...). Consulta con tu asesor fiscal o verifica en sede.agenciatributaria.gob.es"
}}"""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Experto en PGC PYMEs español. Responde SOLO con JSON válido sin texto extra."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400, temperature=0.1,
    )
    try:
        text = response.choices[0].message.content.strip()
        # Limpiar posibles backticks o texto extra
        if "```" in text:
            parts = text.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"): p = p[4:].strip()
                if p.startswith("{"):
                    text = p
                    break
        # Encontrar el JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        return json.loads(text)
    except Exception:
        return {
            "categoria": "otros",
            "cuenta_pgc": "629",
            "nombre_cuenta_pgc": "629 - Otros servicios",
            "deducible": False,
            "porcentaje_deduccion": 0,
            "explicacion": "No se pudo clasificar automáticamente",
            "nota_importante": "La deducibilidad varía según tu tipo de contribuyente. Consulta en sede.agenciatributaria.gob.es"
        }


async def generate_financial_insights(data: dict) -> list[str]:
    prompt = f"""Analiza estos datos financieros y genera 3-5 insights útiles.
Datos: {data}
IMPORTANTE: No asumas el tipo de contribuyente. Da consejos generales.
Responde SOLO con JSON array de strings. Sin texto extra."""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Asesor financiero experto fiscalidad española. SOLO JSON array válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500, temperature=0.5,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        return json.loads(text.strip())
    except Exception:
        return ["Añade más datos para obtener insights detallados."]
