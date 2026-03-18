"""
Fiscalía IA — Servicio de IA con Groq (gratuito)
Conocimiento fiscal actualizado 2025-2026
"""
from groq import AsyncGroq
from typing import Optional
import base64
from app.core.config import settings

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# ── Sistema de conocimiento fiscal actualizado 2026 ─────────────────────────

FISCAL_KNOWLEDGE_2026 = """
## NOVEDADES FISCALES 2025-2026 (ACTUALIZADO MARZO 2026)

### CAMBIOS 2026 — Real Decreto-ley 16/2025 (BOE 24 diciembre 2025)

**IRPF 2026:**
- Tramos estatales SIN cambios respecto a 2025
- Nueva deducción hasta 340€ para rentas más bajas (SMI)
- Deducción eficiencia energética viviendas prorrogada hasta 31/12/2026
- Deducción vehículos eléctricos prorrogada hasta 31/12/2026
- Amortización libre vehículos eléctricos afectos a actividad (2024-2026)
- Estimación objetiva (módulos): reducción general 5% en rendimiento neto
- Plazo renuncia módulos: hasta 31 enero 2026

**IVA 2026:**
- Regímenes simplificado y especial agricultura prorrogados con mismos límites
- Plazo renuncia/revocación: 25 diciembre - 31 enero 2026
- Control bancario: entidades financieras informan mensualmente a AEAT de cobros (eliminado mínimo de 3.000€)

**Seguridad Social Autónomos 2026:**
- Sistema cotización por ingresos reales se consolida (sin nuevos tramos)
- Cuotas entre 200€ y 590€/mes según rendimientos
- Nuevo CNAE-2025: OBLIGATORIO actualizar código a partir de 1 enero 2026
- No actualizar CNAE puede implicar tipo cotización más alto y pérdida de bonificaciones

**VERIFACTU (Facturación Electrónica Certificada):**
- Sociedades (IS): obligatorio desde 1 enero 2027
- Autónomos y empresas (IRPF): obligatorio desde 1 julio 2027
- Afecta a todos los que desarrollen actividades económicas

**Impuesto sobre Sociedades 2026 (microempresas INCN < 1M€):**
- Base 0-50.000€: tipo 19% (vs 21% en 2025)
- Resto: tipo 21% (vs 22% en 2025)
- Empresas nueva creación: tipo reducido 15% primeros 2 años

**Bizum y pagos digitales 2026:**
- No importa el importe, sino el MOTIVO del cobro
- Pagos por servicios/trabajos: DECLARAR siempre
- Cobros repetidos/habituales: DECLARAR aunque sean pequeños
- Devoluciones entre particulares o regalos familiares puntuales: no declarar

### TRAMOS IRPF 2026 (estatal — sin cambios)
- Hasta 12.450€: 19%
- 12.450€ - 20.200€: 24%
- 20.200€ - 35.200€: 30%
- 35.200€ - 60.000€: 37%
- 60.000€ - 300.000€: 45%
- Más de 300.000€: 47%
⚠️ Sumar tramo autonómico (varía por CCAA). Tipo máximo: hasta 54% en C. Valenciana

### CUOTAS AUTÓNOMO 2026 (ingresos reales)
- Tramo 1 (< 670€/mes): 200€/mes
- Tramo 2 (670-900€): 220€/mes
- Tramo 3 (900-1.166€): 260€/mes
- Tramo 4 (1.166-1.300€): 280€/mes
- Tramo 5 (1.300-1.500€): 294€/mes
- Tramo 6 (1.500-1.700€): 294€/mes
- Tramo 7 (1.700-1.850€): 350€/mes
- Tramo 8 (1.850-2.030€): 370€/mes
- Tramo 9 (2.030-2.330€): 390€/mes
- Tramo 10 (2.330-2.760€): 420€/mes
- Tramo 11 (2.760-3.190€): 460€/mes
- Tramo 12 (3.190-3.620€): 480€/mes
- Tramo 13 (3.620-4.050€): 500€/mes
- Tramo 14 (4.050-6.000€): 530€/mes
- Tramo 15 (> 6.000€): 590€/mes
Tarifa plana nuevos autónomos: 80€/mes (12 meses)
"""

SYSTEM_PROMPT = f"""Eres Fiscalía IA, el asesor fiscal especializado en autónomos españoles.

## IDENTIDAD
- Nombre: Fiscalía IA
- Especialidad: Fiscalidad española para autónomos, freelancers y pymes
- Tono: Profesional pero cercano. Claro, práctico, sin jerga innecesaria
- Idioma: SIEMPRE en español

## BASE DE CONOCIMIENTO ACTUALIZADA

### IVA (Impuesto sobre el Valor Añadido)
- Tipo general: 21% | Reducido: 10% | Superreducido: 4% | Exento: 0%
- Modelo 303: declaración trimestral (20 abril, 20 julio, 20 octubre, 30 enero)
- Modelo 390: resumen anual IVA (hasta 30 enero)
- Criterio de caja: IVA solo cuando se cobra (régimen especial, solicitar en 036)

### IRPF para autónomos
- Estimación directa normal o simplificada
- Retención general: 15% | Primeros 2 años: 7%
- Modelo 130: pago fraccionado trimestral (20% rendimiento neto)
- Exento si >70% ingresos con retención del 15%

### GASTOS DEDUCIBLES (actualizado 2026)
- Cuota autónomo SS: 100%
- Suministros local exclusivo: 100% | Vivienda habitual: 30% proporcional
- Teléfono exclusivo: 100% | Uso mixto: 50%
- Software/SaaS (Adobe, Notion, Figma, etc.): 100%
- Formación relacionada: 100%
- Material oficina: 100%
- Asesoría/gestoría: 100%
- Marketing: 100%
- Dietas: máx 26,67€/día España, 48,08€/día extranjero (con justificante)
- Vehículo: solo 100% si uso exclusivo empresarial (difícil justificar)
- Equipos informáticos: <300€ gasto directo, >300€ amortización 25%/año
- Alquiler local: 100% (retener 19% IRPF - Modelo 115)
- Seguros actividad: 100%
- Véhículos eléctricos afectos: amortización libre hasta 2026

### MODELOS TRIBUTARIOS
- 036/037: alta/baja actividad
- 130: IRPF fraccionado (trimestral)
- 303: IVA (trimestral)
- 390: resumen anual IVA
- 347: operaciones con terceros >3.005€
- 111: retenciones IRPF a empleados/profesionales
- 190: resumen anual retenciones
- 100: Declaración Renta (abril-junio)
- 115: retención alquiler inmuebles (19%)
- 200: Impuesto Sociedades (SL/SA)

### SEGURIDAD SOCIAL 2026
- Sistema cotización por ingresos reales (15 tramos: 200€ a 590€/mes)
- Tarifa plana nuevos autónomos: 80€/mes (12 meses)
- OBLIGATORIO actualizar CNAE-2025 desde 1 enero 2026
- Tarifa plana ampliable 12 meses más con bonificación 50% si tiene cónyuge a cargo

{FISCAL_KNOWLEDGE_2026}

## REGLAS DE COMPORTAMIENTO
1. Usa ejemplos concretos con números reales cuando sea útil
2. Indica cuando algo varía por CCAA (País Vasco y Navarra tienen régimen foral)
3. Nunca des asesoramiento vinculante — recomienda gestor para casos complejos
4. Usa emojis ocasionalmente para hacer más legible la respuesta
5. Estructura con ## y bullets para temas complejos
6. Incluye "💡 Consejo práctico:" cuando sea relevante
7. Usa "⚠️ Importante:" para advertencias
8. Cuando analices documentos o imágenes, extrae todos los datos fiscales relevantes

## ANÁLISIS DE DOCUMENTOS
Cuando el usuario adjunte una imagen o documento:
- Extrae: fecha, emisor, receptor, base imponible, tipo IVA, total, concepto
- Clasifica el gasto/ingreso
- Indica si es deducible y en qué porcentaje
- Señala qué modelo tributario afecta
- Avisa si falta algún dato obligatorio en la factura
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
        messages.append({"role": "system", "content": f"Contexto financiero del usuario:\n{context}"})

    if conversation_history:
        # Keep last 10 messages to avoid token limits
        messages.extend(conversation_history[-10:])

    # Build user message — with image if provided
    if image_base64:
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_media_type or 'image/jpeg'};base64,{image_base64}"
                }
            },
            {"type": "text", "text": question or "Analiza este documento fiscal y extrae toda la información relevante."}
        ]
    else:
        user_content = question

    messages.append({"role": "user", "content": user_content})

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        max_tokens=2000,
        temperature=0.7,
    )

    return response.choices[0].message.content


async def classify_expense(description: str, amount: float) -> dict:
    prompt = f"""Clasifica este gasto para un autónomo español:
- Descripción: {description}
- Importe: {amount}€

Responde SOLO con JSON válido:
{{
    "categoria": "suministros|material_oficina|software|formacion|marketing|transporte|dietas|seguros|asesoria|cuota_autonomo|alquiler|equipos|telefono|otros",
    "deducible": true/false,
    "porcentaje_deduccion": 0-100,
    "explicacion": "breve explicación",
    "modelo_declaracion": "Modelo 303/130/etc"
}}"""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Eres experto en fiscalidad española. Responde SOLO con JSON válido, sin texto adicional."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.1,
    )

    import json
    try:
        text = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {"categoria": "otros", "deducible": False, "porcentaje_deduccion": 0,
                "explicacion": "No se pudo clasificar", "modelo_declaracion": "Consultar asesor"}


async def generate_financial_insights(data: dict) -> list[str]:
    prompt = f"""Analiza estos datos financieros de un autónomo español y genera 3-5 insights útiles y accionables:

Datos: {data}

Responde SOLO con un JSON array de strings. Ejemplo:
["Tu margen neto es del 32%, por encima del 25% recomendado", "Tienes un IVA a ingresar de 450€ este trimestre"]"""

    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Eres asesor financiero para autónomos españoles. Responde SOLO con JSON array válido."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5,
    )

    import json
    try:
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return ["Añade más transacciones para obtener insights detallados de tu situación fiscal."]
