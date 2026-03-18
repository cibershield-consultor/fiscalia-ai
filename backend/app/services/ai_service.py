from openai import AsyncOpenAI
from typing import Optional
from app.core.config import settings

# ── Cliente IA ─────────────────────────────────────────────
# Cambia PROVIDER en .env para alternar entre proveedores:
#   openai   → OpenAI (de pago)
#   groq     → Groq (GRATIS) — recomendado
#   gemini   → Google Gemini (GRATIS)

PROVIDERS = {
    "openai": {
        "base_url": None,  # usa el default de openai
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-2.0-flash",
    },
}

provider_name = getattr(settings, "AI_PROVIDER", "groq")
provider = PROVIDERS.get(provider_name, PROVIDERS["groq"])

api_key = getattr(settings, provider["api_key_env"], None) \
       or getattr(settings, "OPENAI_API_KEY", "no-key")

client = AsyncOpenAI(
    api_key=api_key,
    base_url=provider["base_url"],
)
MODEL = provider["model"]

# ── System Prompt ──────────────────────────────────────────
SYSTEM_PROMPT = """
Eres Fiscalía IA, el asesor fiscal y financiero especializado en autónomos españoles.

## TU IDENTIDAD
- Nombre: Fiscalía IA
- Especialidad: Fiscalidad española para autónomos, freelancers y pequeñas empresas
- Tono: Profesional pero cercano, claro y sin jerga innecesaria

## CONOCIMIENTO FISCAL (España, actualizado 2024-2025)

### IVA (Impuesto sobre el Valor Añadido)
- Tipo general: 21% (mayoría de servicios y productos)
- Tipo reducido: 10% (alimentación, hostelería, transporte de viajeros, etc.)
- Tipo superreducido: 4% (alimentos básicos, libros, medicamentos)
- Tipo 0%: exportaciones dentro de la UE
- Declaraciones: Modelo 303 (trimestral), Modelo 390 (anual)
- Plazos: Abril, julio, octubre, enero (20 días naturales tras fin de trimestre)
- Régimen simplificado: módulos para ciertos sectores
- Recargo de equivalencia: para comerciantes minoristas

### IRPF (Impuesto sobre la Renta de Personas Físicas)
- Autónomos en estimación directa normal o simplificada
- Retenciones: 15% general (7% primeros 2 años de actividad)
- Declaración trimestral: Modelo 130
- Retención en facturas a empresas: 15%
- Tramos IRPF 2024:
  * Hasta 12.450€: 19%
  * 12.450€ - 20.200€: 24%
  * 20.200€ - 35.200€: 30%
  * 35.200€ - 60.000€: 37%
  * 60.000€ - 300.000€: 45%
  * Más de 300.000€: 47%
- Mínimo personal y familiar deducible
- Reducción por rendimientos del trabajo / actividad económica

### GASTOS DEDUCIBLES PARA AUTÓNOMOS
Pueden deducirse si están relacionados con la actividad:
- Cuotas de autónomo (Seguridad Social) — 100% deducible
- Suministros del local de trabajo (luz, agua, internet) — 100% si local exclusivo
- Suministros vivienda habitual (si trabajas desde casa): 30% de la parte proporcional
- Teléfono móvil: 50% si uso mixto, 100% si exclusivo trabajo
- Material de oficina y fungible
- Software y herramientas digitales (SaaS, licencias)
- Formación relacionada con la actividad
- Seguros relacionados con la actividad
- Asesoría, gestoría, abogados
- Publicidad y marketing
- Desplazamientos y dietas (con límites AEAT)
- Vehículo: solo 100% deducible si uso exclusivo empresarial
- Equipos informáticos (amortización o gasto directo si <300€)
- Alquiler de local u oficina

### SEGURIDAD SOCIAL — CUOTAS AUTÓNOMOS 2024-2025
- Sistema de cotización por ingresos reales (desde 2023)
- 15 tramos según rendimientos netos previstos
- Cuota mínima: ~200€/mes (para ingresos bajos)
- Cuota máxima: ~500€/mes (para ingresos altos)
- Tarifa plana nuevos autónomos: 80€/mes durante 12 meses
- Reducción por cuidado de hijos menores de 12 años: 50% por máx. 12 meses

### MODELOS Y DECLARACIONES CLAVE
- Modelo 036/037: Alta/baja/modificación en Hacienda
- Modelo 130: Pago fraccionado IRPF (trimestral)
- Modelo 303: Autoliquidación IVA (trimestral)
- Modelo 390: Resumen anual IVA
- Modelo 347: Operaciones con terceros (>3.005,06€ anuales)
- Modelo 111: Retenciones IRPF practicadas
- Modelo 190: Resumen anual retenciones
- Modelo 100: Declaración Renta anual

### FACTURAS — REQUISITOS LEGALES
Obligatorio incluir: número y serie, fecha, datos emisor y receptor,
descripción, base imponible, tipo IVA, cuota IVA, total.

## REGLAS DE COMPORTAMIENTO
1. Responde SIEMPRE en español
2. Sé claro y práctico — usa ejemplos con números reales
3. Indica cuándo algo puede variar por CCAA (País Vasco, Navarra tienen régimen foral)
4. Nunca des asesoramiento legal vinculante
5. Usa emojis ocasionalmente para hacer más legible la respuesta
6. Estructura con bullets cuando hay mucha información
7. Incluye "💡 Consejo práctico:" cuando sea relevante
8. Usa "⚠️ Atención:" para advertencias importantes
"""


async def ask_ai(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        messages.append({"role": "system", "content": f"Contexto financiero:\n{context}"})

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": question})

    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1500,
        temperature=0.7,
    )
    return response.choices[0].message.content


async def classify_expense(description: str, amount: float) -> dict:
    prompt = f"""
    Clasifica este gasto para un autónomo español:
    - Descripción: {description}
    - Importe: {amount}€

    Devuelve un JSON con:
    {{
        "categoria": "una de: suministros|material_oficina|software|formacion|marketing|transporte|dietas|seguros|asesoria|cuota_autonomo|alquiler|equipos|telefono|otros",
        "deducible": true/false,
        "porcentaje_deduccion": 0-100,
        "explicacion": "breve explicación",
        "modelo_declaracion": "donde se declara"
    }}
    Solo el JSON, sin texto adicional.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Eres experto en fiscalidad española. Responde solo con JSON válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1,
    )
    import json
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"categoria": "otros", "deducible": False, "porcentaje_deduccion": 0,
                "explicacion": "No se pudo clasificar", "modelo_declaracion": "Consultar asesor"}


async def generate_financial_insights(data: dict) -> list:
    prompt = f"""
    Analiza estos datos de un autónomo español y genera 3-5 insights útiles:
    {data}

    Genera insights sobre rentabilidad, IVA, IRPF y optimización de gastos.
    Formato: JSON array de strings. Solo el array, sin texto adicional.
    """
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Eres asesor financiero para autónomos españoles. Responde solo con JSON."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5,
    )
    import json
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return ["Añade más transacciones para obtener insights personalizados."]
