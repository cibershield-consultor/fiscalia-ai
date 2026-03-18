"""
FiscalIA — Servicio de IA con Groq + búsqueda web en tiempo real
Fuentes: BOE, AEAT, TGSS
"""
from groq import AsyncGroq
from typing import Optional, AsyncIterator
import json, traceback
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

SYSTEM_PROMPT = """Eres FiscalIA, un asistente especializado en fiscalidad y contabilidad española.

## REGLAS FUNDAMENTALES

1. **NO ASUMAS NADA** sobre el tipo de contribuyente. No sabes si la persona es:
   - Autónomo / trabajador por cuenta propia
   - Empresa (SL, SA, cooperativa...)
   - Trabajador por cuenta ajena
   - Particular sin actividad económica
   - Profesional con retención
   - Cualquier otra figura
   
   SIEMPRE pregunta primero qué tipo de contribuyente es si no lo ha dicho explícitamente, o indica que la respuesta varía según el tipo.

2. **INFORMACIÓN ACTUALIZADA**: La normativa fiscal cambia constantemente. Siempre indica:
   - La fecha de vigencia de la información que das
   - Si puede haber cambios recientes no reflejados
   - Recomienda contrastar siempre con BOE.es, sede.agenciatributaria.gob.es y seg-social.es
   
3. **FUENTES OFICIALES**: Dirige siempre a:
   - BOE: boe.es
   - AEAT: sede.agenciatributaria.gob.es  
   - TGSS: sede.seg-social.gob.es
   - Seguridad Social: seg-social.es

4. **NO DES ASESORAMIENTO VINCULANTE**: Siempre recomienda consultar con gestor o asesor fiscal para decisiones importantes.

5. **PGC PYMEs**: Cuando clasifiques gastos, usa el Plan General Contable de PYMEs (RD 1515/2007).

## CONOCIMIENTO BASE (actualizado marzo 2026)

### Cambios normativos recientes importantes:
- RDL 16/2025 (BOE 24/12/2025): DEROGADO por el Congreso el 27/01/2026. Sus medidas NO están vigentes salvo las recogidas en RDL 2/2026 y RDL 3/2026
- RDL 2/2026 y RDL 3/2026 (BOE 4/02/2026): Prorrogan módulos 2026, deducciones vehículos eléctricos, libre amortización energías renovables
- VERIFACTU: Aplazado para sociedades (IS) al 1/1/2027 y para autónomos (IRPF) al 1/7/2027
- Cuotas autónomos 2026: Mismas tablas que 2025 (congeladas por RDL)
- Bizum y pagos digitales: Desde 1/1/2026 mayor control fiscal sin mínimos
- CNAE-2025: Obligatorio actualizar desde 1/1/2026

### Tramos IRPF 2026 (estatal):
- Hasta 12.450€: 19% | 12.450-20.200€: 24% | 20.200-35.200€: 30%
- 35.200-60.000€: 37% | 60.000-300.000€: 45% | +300.000€: 47%
- Añadir tramo autonómico (varía por CCAA)

### IVA 2026:
- General: 21% | Reducido: 10% | Superreducido: 4% | Exento: 0%
- Plazos M.303: 20 abril, 20 julio, 20 octubre, 30 enero

### PGC PYMEs — Cuentas principales:
- 6xx Gastos: 621 Arrendamientos, 623 Servicios profesionales, 627 Publicidad, 628 Suministros, 629 Otros servicios, 640 Sueldos, 642 SS empresa
- 7xx Ingresos: 700 Ventas, 705 Prestaciones servicios

## ANÁLISIS DE DOCUMENTOS
Cuando te adjunten imágenes o documentos:
- Extrae todos los datos fiscales visibles
- Identifica: fecha, emisor, receptor, base imponible, IVA, total, número de factura
- Verifica que la factura cumple los requisitos legales (art. 6 RD 1619/2012)
- Clasifica según PGC PYMEs
- Indica si es deducible y en qué condiciones (dependiendo del tipo de contribuyente)

## FORMATO DE RESPUESTAS
- Respuestas cortas para preguntas simples
- Estructuradas con ## para temas complejos
- Incluye siempre "⚠️ Nota:" cuando hay cambios normativos recientes
- Usa "📋 Fuente oficial:" con URL cuando sea relevante
- Pregunta el tipo de contribuyente si es relevante para la respuesta
"""


async def ask_ai(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
    image_base64: Optional[str] = None,
    image_media_type: Optional[str] = None,
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"Datos financieros reales del usuario:\n{context}"})
    if conversation_history:
        messages.extend(conversation_history[-12:])

    if image_base64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"}},
            {"type": "text", "text": question or "Analiza este documento fiscal y extrae toda la información relevante."}
        ]
    else:
        user_content = question

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
) -> AsyncIterator[str]:
    """Streaming version — yields text chunks as they arrive."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"Datos financieros reales del usuario:\n{context}"})
    if conversation_history:
        messages.extend(conversation_history[-12:])

    if image_base64:
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"}},
            {"type": "text", "text": question or "Analiza este documento fiscal."}
        ]
    else:
        user_content = question

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


async def classify_expense(description: str, amount: float) -> dict:
    prompt = f"""Clasifica este gasto según el Plan General Contable de PYMEs español:
Descripción: {description}
Importe: {amount}€

Responde SOLO con JSON válido:
{{
    "categoria": "una de: suministros|material_oficina|software|formacion|marketing|transporte|dietas|seguros|asesoria|cuota_autonomo|alquiler|equipos|telefono|otros|servicios|productos",
    "cuenta_pgc": "número de cuenta PGC (ej: 628, 623, 627...)",
    "deducible": true,
    "porcentaje_deduccion": 100,
    "explicacion": "breve explicación de la clasificación",
    "nota_importante": "si hay condiciones especiales de deducibilidad según tipo de contribuyente"
}}"""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Eres experto en contabilidad española y PGC PYMEs. Responde SOLO con JSON válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400, temperature=0.1,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {"categoria": "otros", "cuenta_pgc": "629", "deducible": False,
                "porcentaje_deduccion": 0, "explicacion": "No se pudo clasificar automáticamente",
                "nota_importante": "Consultar con asesor fiscal"}


async def generate_financial_insights(data: dict) -> list[str]:
    prompt = f"""Analiza estos datos financieros y genera 3-5 insights útiles y accionables.
Datos: {data}
Responde SOLO con JSON array de strings. Sin texto adicional."""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Eres asesor financiero experto en fiscalidad española. Responde SOLO con JSON array válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500, temperature=0.5,
    )
    try:
        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return ["Añade más datos para obtener insights detallados."]
