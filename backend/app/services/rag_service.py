"""
FiscalIA — Motor RAG ligero (sin sentence-transformers, sin ChromaDB)
Búsqueda por TF-IDF + BM25 en memoria + web en tiempo real
RAM total: < 20MB
"""
import json
import math
import re
from datetime import datetime
from typing import Optional
import httpx

# ══════════════════════════════════════════════════════════════
#  BASE DE CONOCIMIENTO EN MEMORIA (sin BD vectorial)
# ══════════════════════════════════════════════════════════════

FISCAL_KNOWLEDGE_BASE = [
    {
        "id": "iva_tipos_2026",
        "text": """IVA España 2026 — Tipos impositivos vigentes:
Tipo general 21%: mayoría de bienes/servicios, ropa, electrónica, servicios profesionales, vehículos.
Tipo reducido 10%: hostelería, restauración, transporte viajeros, determinados alimentos, entradas eventos.
Tipo superreducido 4%: pan, leche, queso, huevos, frutas, verduras, libros, medicamentos, prótesis.
Exento 0%: exportaciones, operaciones intracomunitarias, servicios médicos, educativos, financieros, seguros.
Modelo 303: declaración trimestral. Plazos: 20 abril, 20 julio, 20 octubre, 30 enero.
Modelo 390: resumen anual IVA, hasta 30 enero año siguiente.
Criterio de caja: IVA cuando se cobra, no cuando se factura. Solicitar en modelo 036.
Recargo de equivalencia: comerciantes minoristas que no transformen productos.""",
        "keywords": ["iva", "impuesto valor añadido", "21%", "10%", "4%", "exento", "tipo", "303", "390", "trimestral", "factura"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/iva.html",
    },
    {
        "id": "irpf_tramos_2026",
        "text": """IRPF 2026 — Tramos estatales (sin cambios):
Hasta 12.450€: 19% | 12.450-20.200€: 24% | 20.200-35.200€: 30%
35.200-60.000€: 37% | 60.000-300.000€: 45% | Más de 300.000€: 47%
IMPORTANTE: Añadir tramo autonómico (varía por CCAA). País Vasco y Navarra tienen régimen foral.
Tipo efectivo siempre menor que el marginal.
Retenciones actividades económicas: 15% general, 7% primeros 2 años de actividad.
Modelo 130: pago fraccionado IRPF autónomos estimación directa, 20% rendimiento neto acumulado.
No obligatorio si más del 70% de ingresos llevan retención del 15%.
Modelo 100: declaración anual renta, campaña abril-junio.""",
        "keywords": ["irpf", "renta", "tramo", "tipo", "19%", "24%", "30%", "37%", "45%", "retención", "130", "100", "estimación directa"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/irpf.html",
    },
    {
        "id": "autonomos_cotizacion_2026",
        "text": """Cotización autónomos 2026 — Sistema por ingresos reales (desde 2023):
15 tramos según rendimientos netos mensuales:
< 670€: 200€/mes | 670-900€: 220€/mes | 900-1.166€: 260€/mes | 1.166-1.300€: 280€/mes
1.300-1.500€: 294€/mes | 1.500-1.700€: 294€/mes | 1.700-1.850€: 350€/mes | 1.850-2.030€: 370€/mes
2.030-2.330€: 390€/mes | 2.330-2.760€: 420€/mes | 2.760-3.190€: 460€/mes | 3.190-3.620€: 480€/mes
3.620-4.050€: 500€/mes | 4.050-6.000€: 530€/mes | > 6.000€: 590€/mes
Tarifa plana nuevos autónomos: 80€/mes primeros 12 meses.
Regularización anual: se ajusta al presentar la renta.
CNAE-2025: obligatorio actualizar código de actividad desde 1 enero 2026.""",
        "keywords": ["autónomo", "cuota", "cotización", "RETA", "seguridad social", "tarifa plana", "80€", "ingresos reales", "tramo", "CNAE"],
        "source": "TGSS", "url": "https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo",
    },
    {
        "id": "gastos_deducibles",
        "text": """Gastos deducibles actividades económicas España 2026:
La deducibilidad depende del tipo de contribuyente y de que el gasto sea necesario para la actividad.
Para autónomos IRPF estimación directa:
- Cuota SS autónomo: 100% siempre deducible.
- Suministros local exclusivo (luz, agua, internet): 100%.
- Suministros vivienda habitual trabajo desde casa: 30% sobre % superficie afecta.
- Teléfono móvil uso exclusivo laboral: 100%. Uso mixto: 50%.
- Software y SaaS (Adobe, Notion, etc.): 100% si uso profesional.
- Formación relacionada con la actividad: 100%.
- Gestoría, asesoría, abogados: 100%.
- Marketing y publicidad: 100%.
- Dietas: máx. 26,67€/día España, 48,08€/día extranjero. Con justificante, fuera municipio habitual.
- Vehículo: solo 100% si uso exclusivo empresarial (muy difícil de justificar ante AEAT).
- Equipos informáticos: < 300€ gasto directo; > 300€ amortización 25%/año.
- Alquiler local: 100% (retener 19% IRPF al arrendador, Modelo 115).
Para empresas IS: gastos contabilizados relacionados con actividad son deducibles salvo limitaciones legales.""",
        "keywords": ["deducible", "gasto", "deducir", "teléfono", "suministros", "local", "vehículo", "formación", "dietas", "software", "gestoría"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/irpf/deducciones-gastos.html",
    },
    {
        "id": "modelos_plazos",
        "text": """Modelos fiscales España 2026 — Plazos:
TRIMESTRALES (T1 ene-mar, T2 abr-jun, T3 jul-sep, T4 oct-dic):
Modelo 303 (IVA): 20 abril, 20 julio, 20 octubre, 30 enero.
Modelo 130 (IRPF pago fraccionado autónomos): mismos plazos.
Modelo 111 (retenciones trabajo/actividades): mismos plazos.
Modelo 115 (retención alquileres): mismos plazos.
ANUALES:
Modelo 390 (resumen anual IVA): hasta 30 enero.
Modelo 190 (resumen retenciones): hasta 31 enero.
Modelo 347 (operaciones con terceros > 3.005,06€): febrero.
Modelo 100 (renta IRPF): campaña abril-junio.
Modelo 200 (Impuesto Sociedades): 25 días tras 6 meses del cierre.
CENSALES: Modelo 036/037: alta, modificación o baja en Hacienda.""",
        "keywords": ["modelo", "303", "130", "111", "115", "390", "190", "347", "100", "200", "036", "plazo", "trimestral", "anual", "declaración"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html",
    },
    {
        "id": "novedades_2026",
        "text": """Novedades fiscales España 2026:
RDL 16/2025 (BOE 24/12/2025): DEROGADO por el Congreso el 27/01/2026. Sus medidas NO están vigentes.
Vigente: RDL 2/2026 y RDL 3/2026 (BOE 4/02/2026): prorrogan módulos 2026, deducción vehículos eléctricos, libre amortización renovables.
VERIFACTU (facturación verificable): Sociedades (IS) desde 1/1/2027. Autónomos (IRPF) desde 1/7/2027. Aplazado.
CNAE-2025: obligatorio actualizar código actividad en SS desde 1/1/2026. No hacerlo puede implicar cotización incorrecta.
Bizum y pagos digitales: desde 1/1/2026 mayor control AEAT. Cobros por servicios deben declararse.
Cuotas autónomos 2026: congeladas, mismas tablas que 2025.
IVA alimentos: tipo reducido en revisión, consultar BOE vigente.""",
        "keywords": ["novedad", "2026", "cambio", "verifactu", "CNAE", "RDL", "derogado", "bizum", "actualización", "normativa"],
        "source": "BOE/AEAT", "url": "https://www.boe.es/buscar/boe.php",
    },
    {
        "id": "impuesto_sociedades",
        "text": """Impuesto sobre Sociedades España 2026:
Tipo general: 25%.
Microempresas (INCN < 1M€): base 0-50.000€ al 19%, resto al 21%.
Entidades nueva creación (primeros 2 ejercicios con base positiva): 15%.
Cooperativas fiscalmente protegidas: 20%.
Entidades sin fines lucrativos (Ley 49/2002): 10%.
Limitación gastos financieros: 30% beneficio operativo (EBITDA fiscal). Mínimo deducible 1M€.
Amortizaciones según tablas reglamentarias. Libertad amortización I+D y elementos < 300€.
Gastos no deducibles: multas, sanciones, donativos sin amparo legal.
Modelo 200: autoliquidación anual. 25 días tras 6 meses del cierre.
Modelo 202: pagos fraccionados (obligatorio si cuota > 6.000€).""",
        "keywords": ["sociedades", "SL", "SA", "empresa", "25%", "IS", "impuesto", "200", "202", "microempresa", "15%"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/impuesto-sociedades.html",
    },
    {
        "id": "pgc_pymes",
        "text": """Plan General Contable PYMEs (RD 1515/2007) — Cuentas principales:
GASTOS (grupo 6): 600-602 Compras existencias | 621 Arrendamientos y cánones | 622 Reparaciones
623 Servicios profesionales independientes (gestores, abogados, consultores)
624 Transportes | 625 Seguros | 626 Servicios bancarios
627 Publicidad, propaganda y relaciones públicas
628 Suministros (electricidad, agua, gas, internet, teléfono fijo)
629 Otros servicios (SaaS, suscripciones, servicios varios)
640 Sueldos y salarios | 642 Seguridad Social empresa | 680-681 Amortizaciones
INGRESOS (grupo 7): 700 Ventas mercaderías | 705 Prestaciones servicios
740 Subvenciones explotación | 760 Ingresos financieros
Facturas: número, fecha, datos emisor/receptor, descripción, base imponible, tipo y cuota IVA.""",
        "keywords": ["PGC", "plan contable", "cuenta", "628", "623", "627", "629", "640", "705", "contabilidad", "asiento", "factura"],
        "source": "BOE", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2007-19966",
    },
    {
        "id": "tipos_contribuyentes",
        "text": """Tipos de contribuyentes España — Diferencias fiscales:
AUTÓNOMO (trabajador por cuenta propia): tributa IRPF (estimación directa o módulos), no IS.
Cotiza RETA. Emite facturas con IVA. Modelos: 036/037, 303, 130, 390, 100.
EMPRESA (SL, SA, cooperativa): tributa IS, no IRPF. Trabajadores en Régimen General SS.
Modelos: 200, 202, 303, 390, 111, 190, 347.
TRABAJADOR CUENTA AJENA: tributa IRPF mediante retenciones nómina. NO cobra IVA.
No presenta 303 ni 130. Puede presentar 100 (declaración renta). Gastos deducibles muy limitados.
PROFESIONAL CON RETENCIÓN: autónomo con retención 15% (7% primeros 2 años). Puede estar exento de M.130.
SOCIEDAD CIVIL/COMUNIDAD DE BIENES: atribución de rentas a socios. Cada socio tributa en su IRPF.""",
        "keywords": ["autónomo", "empresa", "trabajador", "asalariado", "SL", "SA", "comunidad bienes", "sociedad civil", "cuenta ajena", "perfil"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es",
    },
    {
        "id": "facturacion_requisitos",
        "text": """Facturación en España — Requisitos legales (RD 1619/2012):
Toda factura debe incluir obligatoriamente:
1. Número y serie (correlativa).
2. Fecha de expedición.
3. Nombre y apellidos/razón social del emisor.
4. NIF del emisor.
5. Datos del destinatario (si es empresa o pide factura).
6. Descripción de los bienes o servicios.
7. Base imponible.
8. Tipo impositivo de IVA aplicado.
9. Cuota de IVA.
10. Total de la factura.
Factura simplificada (ticket): para importes < 400€ IVA incluido o comercio al por menor.
Factura electrónica: legalmente equivalente a papel si garantiza autenticidad e integridad.
VERIFACTU obligatorio: empresas IS desde 1/1/2027, autónomos IRPF desde 1/7/2027.""",
        "keywords": ["factura", "requisito", "obligatorio", "NIF", "IVA", "número", "serie", "emisor", "receptor", "simplificada", "electrónica"],
        "source": "AEAT/BOE", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696",
    },
]

# ── BM25-like scoring (lightweight keyword search) ────────────

def _tokenize(text: str) -> list[str]:
    """Simple Spanish tokenizer — lowercase, remove accents, split words."""
    text = text.lower()
    # Normalize accents
    replacements = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n"}
    for a, b in replacements.items():
        text = text.replace(a, b)
    return re.findall(r'\b\w{2,}\b', text)


def _score_document(query_tokens: list[str], doc: dict) -> float:
    """Score document relevance using keyword + BM25-inspired scoring."""
    score = 0.0
    doc_text = (doc["text"] + " " + " ".join(doc.get("keywords", []))).lower()
    doc_tokens = _tokenize(doc_text)

    # Token frequency in document
    token_freq = {}
    for t in doc_tokens:
        token_freq[t] = token_freq.get(t, 0) + 1

    doc_len = len(doc_tokens)
    avg_len = 300  # approximate average doc length

    for qt in query_tokens:
        # BM25 parameters
        k1, b = 1.5, 0.75
        tf = token_freq.get(qt, 0)
        if tf > 0:
            # BM25 term score
            tf_score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_len))
            score += tf_score

        # Bonus for keyword match (pre-defined important terms)
        if qt in [k.lower() for k in doc.get("keywords", [])]:
            score += 2.0

    # Normalize by query length
    if query_tokens:
        score /= len(query_tokens)

    return score


def search_knowledge_base(query: str, n_results: int = 3) -> list[dict]:
    """Search in-memory knowledge base using BM25-like scoring."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return FISCAL_KNOWLEDGE_BASE[:n_results]

    scored = []
    for doc in FISCAL_KNOWLEDGE_BASE:
        score = _score_document(query_tokens, doc)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:n_results]]


# ══════════════════════════════════════════════════════════════
#  FUENTES WEB EN TIEMPO REAL
# ══════════════════════════════════════════════════════════════

async def search_boe_realtime(query: str, max_results: int = 2) -> list[dict]:
    """Search BOE API for recent legislation."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://www.boe.es/api/api.php",
                params={"op": "search", "query": query, "lang": "es", "numres": max_results, "sort": "date"}
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("response", {}).get("results", {}).get("result", [])
                if isinstance(items, dict): items = [items]
                results = []
                for item in items[:max_results]:
                    results.append({
                        "text": f"BOE {item.get('fecha_publicacion','')}: {item.get('titulo','')}",
                        "source": "BOE",
                        "url": f"https://www.boe.es/buscar/doc.php?id={item.get('identificador','')}",
                    })
                return results
    except Exception:
        pass
    return []


def get_aeat_references(query: str) -> list[dict]:
    """Return relevant AEAT page references based on query keywords."""
    q = query.lower()
    refs = []
    pages = [
        (["iva","303","390","repercutido","soportado"], "AEAT — IVA",
         "https://sede.agenciatributaria.gob.es/Sede/iva.html"),
        (["irpf","renta","100","130","retención","tramo"], "AEAT — IRPF",
         "https://sede.agenciatributaria.gob.es/Sede/irpf.html"),
        (["sociedad","IS","200","202","empresa"], "AEAT — Impuesto Sociedades",
         "https://sede.agenciatributaria.gob.es/Sede/impuesto-sociedades.html"),
        (["plazo","calendario","fecha","modelo","presentar"], "AEAT — Calendario contribuyente",
         "https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html"),
        (["deducible","gasto","deducir"], "AEAT — Deducciones y gastos",
         "https://sede.agenciatributaria.gob.es/Sede/irpf/deducciones-gastos.html"),
        (["autónomo","036","alta","baja"], "AEAT — Autónomos",
         "https://sede.agenciatributaria.gob.es/Sede/autonomos.html"),
    ]
    for keywords, title, url in pages:
        if any(k in q for k in keywords):
            refs.append({"source": "AEAT", "title": title, "url": url})
    if not refs:
        refs.append({"source": "AEAT", "title": "AEAT — Sede electrónica",
                     "url": "https://sede.agenciatributaria.gob.es"})
    return refs[:2]


def get_tgss_references(query: str) -> list[dict]:
    """Return relevant TGSS page references."""
    q = query.lower()
    if any(k in q for k in ["autónomo","cuota","cotiz","RETA","tarifa plana","alta","baja","inem"]):
        return [{"source": "TGSS", "title": "TGSS — Autónomos",
                 "url": "https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo"}]
    return []


# ══════════════════════════════════════════════════════════════
#  MOTOR RAG PRINCIPAL
# ══════════════════════════════════════════════════════════════

async def retrieve_context(query: str, n_results: int = 3) -> list[dict]:
    """
    Retrieve relevant context combining:
    1. In-memory BM25 knowledge base (instant, 0MB extra RAM)
    2. BOE real-time API (optional, graceful fallback)
    3. AEAT/TGSS reference links
    """
    all_context = []

    # 1. Knowledge base search (instant)
    kb_docs = search_knowledge_base(query, n_results)
    for doc in kb_docs:
        all_context.append({
            "text": doc["text"],
            "source": doc["source"],
            "url": doc.get("url", ""),
            "relevance": 1.0,
        })

    # 2. BOE real-time (non-blocking, best-effort)
    try:
        boe_results = await search_boe_realtime(query, max_results=1)
        all_context.extend([{**r, "relevance": 0.6} for r in boe_results])
    except Exception:
        pass

    # 3. AEAT references
    for ref in get_aeat_references(query):
        # Only add if not already covered
        if not any(ref["url"] in c.get("url","") for c in all_context):
            all_context.append({"text": ref["title"], "source": ref["source"],
                               "url": ref["url"], "relevance": 0.5})

    # 4. TGSS references
    for ref in get_tgss_references(query):
        all_context.append({"text": ref["title"], "source": ref["source"],
                            "url": ref["url"], "relevance": 0.5})

    return all_context[:5]


def format_context_for_prompt(context_docs: list[dict]) -> tuple[str, list[dict]]:
    """Format docs into prompt string + references."""
    if not context_docs:
        return "", []
    parts, references = [], []
    for i, doc in enumerate(context_docs, 1):
        parts.append(f"[Fuente {i} — {doc['source']}]\n{doc['text']}")
        if doc.get("url"):
            references.append({"num": i, "source": doc["source"], "url": doc["url"]})
    return "\n\n".join(parts), references


async def initialize_knowledge_base():
    """No-op — knowledge base is in-memory, always ready."""
    print(f"[RAG] Base de conocimiento cargada: {len(FISCAL_KNOWLEDGE_BASE)} documentos (BM25 en memoria)")
