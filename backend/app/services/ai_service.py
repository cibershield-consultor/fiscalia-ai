from openai import AsyncOpenAI
import os
from typing import Optional
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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
- Base de cotización elegida afecta a prestaciones futuras

### MODELOS Y DECLARACIONES CLAVE
- Modelo 036/037: Alta/baja/modificación en Hacienda
- Modelo 130: Pago fraccionado IRPF (trimestral)
- Modelo 303: Autoliquidación IVA (trimestral)
- Modelo 390: Resumen anual IVA
- Modelo 347: Operaciones con terceros (>3.005,06€ anuales)
- Modelo 111: Retenciones IRPF practicadas
- Modelo 190: Resumen anual retenciones
- Modelo 100: Declaración Renta anual
- Modelo 200: Impuesto de Sociedades (para SL/SA)

### FACTURAS — REQUISITOS LEGALES
Obligatorio incluir:
- Número y serie correlativa
- Fecha de expedición
- Datos del emisor (NIF, nombre, dirección)
- Datos del receptor
- Descripción de los servicios/bienes
- Base imponible
- Tipo de IVA aplicado
- Cuota de IVA
- Total factura
- En facturas intracomunitarias: VAT number del cliente

### REGÍMENES ESPECIALES
- Régimen de Módulos (estimación objetiva): para determinadas actividades con ingresos < 250.000€
- Recargo de equivalencia: comerciantes minoristas
- Régimen especial de criterio de caja: IVA solo cuando se cobra
- Régimen de actividades agrícolas y ganaderas
- Autónomos societarios: cuando facturan a través de SL

### DEDUCCIONES Y BENEFICIOS FISCALES 2024-2025
- Plan de pensiones: deducción hasta 1.500€/año (2024)
- Mutualidades: alternativa a SS para algunos colectivos
- Inversión en startups: deducción 50% hasta 100.000€
- Deducción por donativos: 80% primeros 150€, luego 35%
- Reducción por inicio de actividad: 20% primeros 2 años con beneficios
- Compensación de bases imponibles negativas

## REGLAS DE COMPORTAMIENTO
1. Responde SIEMPRE en español
2. Sé claro y práctico — usa ejemplos con números reales
3. Indica SIEMPRE cuándo algo puede variar por CCAA (País Vasco, Navarra tienen régimen foral)
4. Nunca des asesoramiento legal vinculante — recomienda gestor para casos complejos
5. Usa emojis ocasionalmente para hacer más legible la respuesta
6. Estructura con bullets y secciones cuando hay mucha información
7. Si la pregunta es ambigua, haz una aclaración breve y responde lo más probable
8. Actualiza el usuario si algo puede haber cambiado recientemente

## FORMATO DE RESPUESTAS
- Respuestas cortas para preguntas simples
- Respuestas estructuradas con ## y bullets para temas complejos
- Incluye siempre un "💡 Consejo práctico:" cuando sea relevante
- Usa "⚠️ Atención:" para advertencias importantes
- Termina con "¿Tienes alguna duda más?" si la respuesta es larga
"""


async def ask_ai(
    question: str,
    conversation_history: Optional[list] = None,
    context: Optional[str] = None,
) -> str:
    """
    Call OpenAI with full conversation history and optional financial context.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject financial context if available
    if context:
        messages.append({
            "role": "system",
            "content": f"Contexto financiero del usuario:\n{context}"
        })

    # Add conversation history
    if conversation_history:
        messages.extend(conversation_history)

    # Add current question
    messages.append({"role": "user", "content": question})

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=messages,
        max_tokens=1500,
        temperature=0.7,
    )

    return response.choices[0].message.content


async def classify_expense(description: str, amount: float) -> dict:
    """
    Use AI to classify an expense into fiscal categories.
    """
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
        "modelo_declaracion": "donde se declara (ej: Modelo 303, Modelo 130)"
    }}
    Solo el JSON, sin texto adicional.
    """

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Eres un experto en fiscalidad española. Responde solo con JSON válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1,
    )

    import json
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {
            "categoria": "otros",
            "deducible": False,
            "porcentaje_deduccion": 0,
            "explicacion": "No se pudo clasificar automáticamente",
            "modelo_declaracion": "Consultar con asesor"
        }


async def generate_financial_insights(data: dict) -> list[str]:
    """
    Generate AI-powered financial insights for the user's dashboard.
    """
    prompt = f"""
    Analiza estos datos financieros de un autónomo español y genera 3-5 insights útiles:
    
    Datos: {data}
    
    Genera insights sobre:
    - Rentabilidad y márgenes
    - IVA a pagar / recuperar
    - IRPF estimado
    - Gastos inusuales o que se pueden optimizar
    - Comparativa con trimestre anterior si hay datos
    
    Formato: lista JSON de strings, cada uno un insight concreto y accionable.
    Ejemplo: ["Tu margen neto es del 32%, por encima del 25% recomendado", "Tienes un IVA a ingresar de 450€ este trimestre"]
    Solo el JSON array.
    """

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Eres un asesor financiero experto en autónomos españoles. Responde solo con JSON válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5,
    )

    import json
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return ["No se pudieron generar insights con los datos actuales."]
