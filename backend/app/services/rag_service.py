"""
FiscalIA — Motor RAG (Retrieval-Augmented Generation)
Combina base de conocimiento vectorial + búsqueda web en tiempo real
Fuentes: BOE, AEAT, Seguridad Social
"""
import json
import hashlib
import re
from datetime import datetime
from typing import Optional
import httpx
import chromadb
from chromadb.utils import embedding_functions

# ── ChromaDB con embeddings multilingüe gratuitos ─────────────
_chroma_client = None
_collection = None

EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path="./rag_db")
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
        _collection = _chroma_client.get_or_create_collection(
            name="fiscalia_knowledge",
            embedding_function=ef,
            metadata={"description": "Base de conocimiento fiscal española"}
        )
    return _collection


# ══════════════════════════════════════════════════════════════
#  FUENTES WEB EN TIEMPO REAL
# ══════════════════════════════════════════════════════════════

SOURCES = {
    "boe_api": "https://www.boe.es/api/api.php",
    "aeat_noticias": "https://www.agenciatributaria.es/AEAT/Contenidos_Comunes/La_Agencia_Tributaria/Novedades/",
    "ss_noticias": "https://www.seg-social.es/wps/portal/wss/internet/Noticias",
}

async def search_boe_realtime(query: str, max_results: int = 3) -> list[dict]:
    """Search BOE API for recent legislation."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            params = {
                "op": "search",
                "query": query,
                "lang": "es",
                "numres": max_results,
                "sort": "date",
            }
            r = await client.get(SOURCES["boe_api"], params=params)
            if r.status_code == 200:
                data = r.json()
                items = data.get("response", {}).get("results", {}).get("result", [])
                if isinstance(items, dict):
                    items = [items]
                for item in items[:max_results]:
                    results.append({
                        "source": "BOE",
                        "title": item.get("titulo", ""),
                        "date": item.get("fecha_publicacion", ""),
                        "url": f"https://www.boe.es/buscar/doc.php?id={item.get('identificador','')}",
                        "text": item.get("texto", "") or item.get("titulo", ""),
                        "id": item.get("identificador", ""),
                    })
    except Exception as e:
        # BOE API may be unavailable — not critical
        pass
    return results


async def search_aeat_realtime(query: str) -> list[dict]:
    """Search AEAT for relevant fiscal information."""
    results = []
    # Key AEAT pages by topic
    aeat_pages = {
        "iva": ("IVA — AEAT", "https://sede.agenciatributaria.gob.es/Sede/iva.html",
                "Información sobre IVA: tipos impositivos, modelos 303 y 390, plazos de presentación."),
        "irpf": ("IRPF — AEAT", "https://sede.agenciatributaria.gob.es/Sede/irpf.html",
                 "Información sobre IRPF: tramos, retenciones, modelos 100 y 130."),
        "sociedades": ("Impuesto Sociedades — AEAT",
                       "https://sede.agenciatributaria.gob.es/Sede/impuesto-sociedades.html",
                       "Información sobre Impuesto de Sociedades: tipo general 25%, modelo 200."),
        "autonomos": ("Autónomos — AEAT",
                      "https://sede.agenciatributaria.gob.es/Sede/autonomos.html",
                      "Guía para autónomos: alta, modelos tributarios, estimación directa."),
        "modelos": ("Modelos fiscales — AEAT",
                    "https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI01.shtml",
                    "Modelos y formularios tributarios: 036, 037, 111, 115, 130, 190, 303, 347, 390."),
        "calendario": ("Calendario contribuyente — AEAT",
                       "https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html",
                       "Plazos y fechas clave para presentar declaraciones fiscales."),
        "deducciones": ("Deducciones — AEAT",
                        "https://sede.agenciatributaria.gob.es/Sede/irpf/deducciones-gastos.html",
                        "Gastos deducibles y deducciones aplicables según actividad económica."),
    }

    q_lower = query.lower()
    for key, (title, url, desc) in aeat_pages.items():
        if key in q_lower or any(w in q_lower for w in key.split()):
            results.append({"source": "AEAT", "title": title, "url": url,
                           "text": desc, "date": datetime.now().strftime("%Y")})

    # Always include general AEAT reference
    if not results:
        results.append({
            "source": "AEAT",
            "title": "Sede electrónica AEAT",
            "url": "https://sede.agenciatributaria.gob.es",
            "text": "Portal oficial de la Agencia Tributaria española. Acceso a trámites, modelos y consultas.",
            "date": datetime.now().strftime("%Y"),
        })
    return results[:2]


async def search_ss_realtime(query: str) -> list[dict]:
    """Return relevant Social Security pages."""
    q_lower = query.lower()
    ss_pages = {
        "autonomo": ("Autónomos — TGSS",
                     "https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo",
                     "Información sobre cotización de autónomos por ingresos reales, tramos 2026, tarifa plana 80€."),
        "cotizacion": ("Cotización — TGSS",
                       "https://www.seg-social.es/wps/portal/wss/internet/Trabajadores/CotizacionRecaudacionTrabajadores",
                       "Bases y tipos de cotización a la Seguridad Social. Tablas de cuotas."),
        "baja": ("Incapacidad temporal — TGSS",
                 "https://sede.seg-social.gob.es/wps/portal/sede/sede/Ciudadanos/Incapacidad+Temporal",
                 "Prestación por incapacidad temporal, plazos y condiciones."),
    }
    results = []
    for key, (title, url, desc) in ss_pages.items():
        if key in q_lower:
            results.append({"source": "TGSS", "title": title, "url": url,
                           "text": desc, "date": "2026"})
    if not results and any(w in q_lower for w in ["seguridad social","cuota","cotiz","alta","baja"]):
        results.append({
            "source": "TGSS",
            "title": "Sede TGSS — Tesorería General Seguridad Social",
            "url": "https://sede.seg-social.gob.es",
            "text": "Portal oficial de la Tesorería General de la Seguridad Social.",
            "date": "2026",
        })
    return results[:2]


# ══════════════════════════════════════════════════════════════
#  BASE VECTORIAL — Documentos fiscales pre-cargados
# ══════════════════════════════════════════════════════════════

FISCAL_KNOWLEDGE_BASE = [
    # IVA
    {
        "id": "iva_tipos_2026",
        "text": """IVA en España 2026 — Tipos impositivos vigentes:
- Tipo general: 21% — Aplica a mayoría de bienes y servicios: ropa, electrodomésticos, servicios profesionales, vehículos.
- Tipo reducido: 10% — Hostelería, restauración, transporte de viajeros, determinados alimentos, entradas eventos.
- Tipo superreducido: 4% — Pan, leche, queso, huevos, frutas, verduras, libros, medicamentos, prótesis.
- Exento (0%): Exportaciones extracomunitarias, operaciones intracomunitarias, servicios médicos, educativos, financieros, seguros.
Modelo 303: Declaración trimestral IVA — Plazos: 20 abril (T1), 20 julio (T2), 20 octubre (T3), 30 enero (T4).
Modelo 390: Resumen anual IVA — Hasta 30 enero año siguiente.
Criterio de caja: IVA cuando se cobra, no cuando se factura. Solicitar en modelo 036.
Fuente: AEAT — https://sede.agenciatributaria.gob.es/Sede/iva.html""",
        "metadata": {"tema": "iva", "año": "2026", "fuente": "AEAT"},
    },
    # IRPF
    {
        "id": "irpf_tramos_2026",
        "text": """IRPF 2026 — Tramos estatales (sin cambios respecto 2025):
- Hasta 12.450€: 19%
- 12.450€ - 20.200€: 24%
- 20.200€ - 35.200€: 30%
- 35.200€ - 60.000€: 37%
- 60.000€ - 300.000€: 45%
- Más de 300.000€: 47%
IMPORTANTE: A estos tipos se añade el tramo autonómico (varía por CCAA). Tipo efectivo siempre menor que el marginal.
País Vasco y Navarra tienen régimen foral propio con tipos diferentes.
Retenciones para actividades económicas: 15% general, 7% primeros 2 años de actividad.
Modelo 130: Pago fraccionado IRPF para autónomos en estimación directa — 20% rendimiento neto acumulado.
Modelo 100: Declaración anual renta — Campaña abril-junio.
Fuente: AEAT — https://sede.agenciatributaria.gob.es/Sede/irpf.html""",
        "metadata": {"tema": "irpf", "año": "2026", "fuente": "AEAT"},
    },
    # Autónomos SS
    {
        "id": "autonomos_cotizacion_2026",
        "text": """Cotización autónomos 2026 — Sistema por ingresos reales (vigente desde 2023):
15 tramos según rendimientos netos mensuales previstos:
Tramo 1 (< 670€): 200€/mes | Tramo 2 (670-900€): 220€/mes | Tramo 3 (900-1.166€): 260€/mes
Tramo 4 (1.166-1.300€): 280€/mes | Tramo 5 (1.300-1.500€): 294€/mes | Tramo 6 (1.500-1.700€): 294€/mes
Tramo 7 (1.700-1.850€): 350€/mes | Tramo 8 (1.850-2.030€): 370€/mes | Tramo 9 (2.030-2.330€): 390€/mes
Tramo 10 (2.330-2.760€): 420€/mes | Tramo 11 (2.760-3.190€): 460€/mes | Tramo 12 (3.190-3.620€): 480€/mes
Tramo 13 (3.620-4.050€): 500€/mes | Tramo 14 (4.050-6.000€): 530€/mes | Tramo 15 (> 6.000€): 590€/mes
Tarifa plana nuevos autónomos: 80€/mes durante los primeros 12 meses.
Regularización anual: Se ajusta la cuota a los ingresos reales al presentar la declaración de renta.
CNAE-2025: Obligatorio actualizar código de actividad desde 1 enero 2026.
Fuente: TGSS — https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo""",
        "metadata": {"tema": "autonomos", "año": "2026", "fuente": "TGSS"},
    },
    # Gastos deducibles
    {
        "id": "gastos_deducibles_general",
        "text": """Gastos deducibles en actividades económicas — España 2026:
La deducibilidad depende del tipo de contribuyente y de que el gasto sea necesario para la actividad.

Para autónomos (IRPF, estimación directa):
- Cuota Seguridad Social autónomo: 100% deducible siempre.
- Suministros local exclusivo (luz, agua, internet): 100% deducible.
- Suministros vivienda habitual (trabajo desde casa): 30% sobre % superficie afecta.
- Teléfono móvil uso exclusivo laboral: 100%. Uso mixto: 50%.
- Software y SaaS (Adobe, Notion, etc.): 100% si uso profesional.
- Formación relacionada: 100%.
- Servicios profesionales (gestoría, abogados): 100%.
- Marketing y publicidad: 100%.
- Dietas: máx. 26,67€/día en España, 48,08€/día extranjero. Con justificante y fuera municipio habitual.
- Vehículo: Solo 100% si uso exclusivo empresarial (muy difícil de justificar ante AEAT).
- Equipos informáticos: < 300€ gasto directo; > 300€ amortización (25%/año para equipos informáticos).
- Alquiler local: 100% (retener 19% IRPF al arrendador, Modelo 115).

Para empresas (Impuesto Sociedades):
- Gastos contabilizados y relacionados con la actividad: deducibles salvo limitaciones.
- Gastos de representación: limitados.
- Donativos: con límites según normativa IS.

PGC PYMEs: Cuenta 628 suministros, 623 servicios profesionales, 627 publicidad, 621 arrendamientos.
Fuente: AEAT — https://sede.agenciatributaria.gob.es/Sede/irpf/deducciones-gastos.html""",
        "metadata": {"tema": "gastos_deducibles", "año": "2026", "fuente": "AEAT"},
    },
    # Modelos fiscales
    {
        "id": "modelos_fiscales_plazos",
        "text": """Modelos fiscales España — Plazos 2026:

TRIMESTRALES (T1: ene-mar, T2: abr-jun, T3: jul-sep, T4: oct-dic):
- Modelo 303 (IVA): 20 abril, 20 julio, 20 octubre, 30 enero.
- Modelo 130 (IRPF pago fraccionado autónomos estimación directa): mismos plazos.
- Modelo 131 (IRPF pago fraccionado autónomos módulos): mismos plazos.
- Modelo 111 (retenciones rendimientos trabajo/actividades): mismos plazos.
- Modelo 115 (retención alquileres): mismos plazos.

ANUALES:
- Modelo 390 (resumen anual IVA): hasta 30 enero.
- Modelo 190 (resumen retenciones): hasta 31 enero.
- Modelo 347 (operaciones con terceros > 3.005,06€): febrero.
- Modelo 100 (renta IRPF): campaña abril-junio.
- Modelo 200 (Impuesto Sociedades): 25 días tras 6 meses del cierre ejercicio.

CENSALES:
- Modelo 036/037: alta, modificación o baja en Hacienda.
Fuente: AEAT — https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html""",
        "metadata": {"tema": "modelos", "año": "2026", "fuente": "AEAT"},
    },
    # Novedades 2026
    {
        "id": "novedades_2026",
        "text": """Novedades fiscales España 2026 — Cambios normativos relevantes:

RDL 16/2025 (BOE 24/12/2025): DEROGADO por el Congreso el 27/01/2026.
Las medidas vigentes son las recogidas en:
- RDL 2/2026 (BOE 4/02/2026): Prorroga módulos 2026, deducción vehículos eléctricos, libre amortización renovables.
- RDL 3/2026 (BOE 4/02/2026): Medidas adicionales de apoyo a contribuyentes.

VERIFACTU (Facturación verificable):
- Sociedades obligadas desde 1/1/2027 (aplazado).
- Autónomos/personas físicas desde 1/7/2027 (aplazado).
- Afecta a todos los que emitan facturas en actividades económicas.

CNAE-2025: Nuevo clasificador de actividades económicas. Obligatorio actualizar en SS desde 1/1/2026. No actualizar puede implicar cotización incorrecta y pérdida de bonificaciones.

Bizum y pagos digitales: Desde 1/1/2026, mayor control por parte de la AEAT. Los cobros por servicios o trabajos deben declararse independientemente del importe.

IVA alimentos: Pendiente de revisión tipo 0% en aceite y pasta. Consultar BOE vigente.
Cuotas autónomos: Congeladas para 2026 (mismas tablas que 2025 por RDL).
Fuente: BOE — https://www.boe.es/buscar/boe.php | AEAT — https://sede.agenciatributaria.gob.es""",
        "metadata": {"tema": "novedades", "año": "2026", "fuente": "BOE/AEAT"},
    },
    # Impuesto Sociedades
    {
        "id": "impuesto_sociedades_2026",
        "text": """Impuesto sobre Sociedades España 2026:
Tipo general: 25%.
Microempresas (INCN < 1M€): 
- Base 0-50.000€: 19% (reducción temporal).
- Resto: 21%.
Entidades nueva creación (primeros 2 ejercicios con base positiva): 15%.
Cooperativas fiscalmente protegidas: 20%.
Entidades sin fines lucrativos (régimen especial Ley 49/2002): 10%.

Gastos no deducibles IS: multas, sanciones, donativos sin amparo legal, gastos de actuaciones contrarias a ordenamiento.
Limitación gastos financieros: 30% del beneficio operativo (EBITDA fiscal). Mínimo deducible 1M€.
Amortizaciones: tablas reglamentarias según tipo de bien. Libertad de amortización para inversiones en I+D y elementos nuevos < 300€.

Modelo 200: Autoliquidación anual. Plazo: 25 días tras 6 meses del cierre.
Modelo 202: Pagos fraccionados (obligatorio si cuota > 6.000€).
Fuente: AEAT — https://sede.agenciatributaria.gob.es/Sede/impuesto-sociedades.html""",
        "metadata": {"tema": "sociedades", "año": "2026", "fuente": "AEAT"},
    },
    # PGC PYMEs
    {
        "id": "pgc_pymes_cuentas",
        "text": """Plan General Contable PYMEs (RD 1515/2007) — Cuentas principales:

GRUPO 6 — GASTOS:
600-602: Compras de existencias | 620: I+D | 621: Arrendamientos y cánones | 622: Reparaciones
623: Servicios de profesionales independientes (gestores, abogados, consultores)
624: Transportes | 625: Primas de seguros | 626: Servicios bancarios
627: Publicidad, propaganda y relaciones públicas
628: Suministros (electricidad, agua, gas, internet, teléfono fijo)
629: Otros servicios (suscripciones SaaS, material diverso, servicios varios)
640: Sueldos y salarios | 642: Seguridad Social a cargo empresa
649: Otros gastos sociales | 660: Gastos financieros | 680-681: Amortizaciones

GRUPO 7 — INGRESOS:
700: Ventas de mercaderías | 701-702: Ventas de productos terminados
705: Prestaciones de servicios | 740: Subvenciones a la explotación
760: Ingresos financieros | 775: Beneficios por enajenación de inmovilizado

Facturas: Deben incluir número, fecha, datos emisor/receptor, descripción, base imponible, tipo y cuota IVA.
Fuente: BOE — RD 1515/2007 | https://www.boe.es/buscar/act.php?id=BOE-A-2007-19966""",
        "metadata": {"tema": "contabilidad", "año": "2026", "fuente": "BOE"},
    },
    # Tipos de contribuyentes
    {
        "id": "tipos_contribuyentes",
        "text": """Tipos de contribuyentes en España — Diferencias fiscales clave:

AUTÓNOMO (Trabajador por cuenta propia):
- Tributa en IRPF (estimación directa o módulos), no en IS.
- Cotiza en Régimen Especial Trabajadores Autónomos (RETA).
- Emite facturas con IVA (salvo exenciones).
- Presenta: Modelo 036/037, 303, 130, 390, 100.

EMPRESA (SL, SA, cooperativa):
- Tributa en Impuesto sobre Sociedades (IS), no en IRPF.
- Trabajadores cotizan en Régimen General SS.
- Socios/administradores pueden cotizar en RETA o RG según circunstancias.
- Presenta: Modelo 200, 202, 303, 390, 111, 190, 347.

TRABAJADOR POR CUENTA AJENA:
- Tributa IRPF mediante retenciones en nómina (no presenta 130).
- NO cobra IVA en nómina.
- No presenta 303, 130. Sí puede presentar 100 (declaración renta).
- Gastos deducibles muy limitados vs autónomo/empresa.

PROFESIONAL CON RETENCIÓN:
- Puede ser autónomo que emite facturas con retención 15% (7% primeros 2 años).
- No está obligado a presentar M.130 si >70% ingresos llevan retención.

SOCIEDAD CIVIL / COMUNIDAD DE BIENES:
- Régimen especial. Atribución de rentas a socios.
- Cada socio tributa en su IRPF por su parte.
Fuente: AEAT — https://sede.agenciatributaria.gob.es""",
        "metadata": {"tema": "contribuyentes", "año": "2026", "fuente": "AEAT"},
    },
]


async def initialize_knowledge_base():
    """Load fiscal knowledge documents into ChromaDB vector store."""
    try:
        col = get_collection()
        existing = col.get()
        existing_ids = set(existing.get("ids", []))
        new_docs = [d for d in FISCAL_KNOWLEDGE_BASE if d["id"] not in existing_ids]

        if new_docs:
            col.add(
                documents=[d["text"] for d in new_docs],
                ids=[d["id"] for d in new_docs],
                metadatas=[d["metadata"] for d in new_docs],
            )
            print(f"[RAG] Cargados {len(new_docs)} documentos en ChromaDB")
        else:
            print(f"[RAG] ChromaDB ya tiene {len(existing_ids)} documentos")
    except Exception as e:
        print(f"[RAG] Error inicializando ChromaDB: {e}")


async def add_document_to_kb(doc_id: str, text: str, metadata: dict):
    """Add a new document to the knowledge base."""
    col = get_collection()
    try:
        col.add(documents=[text], ids=[doc_id], metadatas=[metadata])
        return True
    except Exception:
        col.update(documents=[text], ids=[doc_id], metadatas=[metadata])
        return True


# ══════════════════════════════════════════════════════════════
#  MOTOR RAG — Búsqueda y recuperación
# ══════════════════════════════════════════════════════════════

async def retrieve_context(query: str, n_results: int = 4) -> list[dict]:
    """
    Retrieve relevant context from vector DB + real-time web sources.
    Returns list of {text, source, url} dicts.
    """
    all_context = []

    # 1. Vector search in ChromaDB
    try:
        col = get_collection()
        results = col.query(
            query_texts=[query],
            n_results=min(n_results, col.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            # Only use if reasonably relevant (distance < 1.5)
            if dist < 1.5:
                all_context.append({
                    "text": doc,
                    "source": meta.get("fuente", "Base de conocimiento"),
                    "url": "",
                    "tema": meta.get("tema", ""),
                    "relevance": round(1 - dist/2, 2),
                })
    except Exception as e:
        print(f"[RAG] ChromaDB search error: {e}")

    # 2. Real-time BOE search
    boe_results = await search_boe_realtime(query)
    for r in boe_results:
        all_context.append({
            "text": f"BOE {r['date']}: {r['title']}\n{r['text']}",
            "source": "BOE",
            "url": r["url"],
            "relevance": 0.7,
        })

    # 3. AEAT relevant pages
    aeat_results = await search_aeat_realtime(query)
    for r in aeat_results:
        all_context.append({
            "text": f"AEAT: {r['title']}\n{r['text']}",
            "source": "AEAT",
            "url": r["url"],
            "relevance": 0.7,
        })

    # 4. SS relevant pages
    ss_results = await search_ss_realtime(query)
    for r in ss_results:
        all_context.append({
            "text": f"TGSS: {r['title']}\n{r['text']}",
            "source": "TGSS",
            "url": r["url"],
            "relevance": 0.65,
        })

    # Sort by relevance and return top results
    all_context.sort(key=lambda x: x.get("relevance", 0), reverse=True)
    return all_context[:6]


def format_context_for_prompt(context_docs: list[dict]) -> tuple[str, list[dict]]:
    """Format retrieved docs into prompt string + references list."""
    if not context_docs:
        return "", []

    parts = []
    references = []

    for i, doc in enumerate(context_docs, 1):
        parts.append(f"[FUENTE {i} — {doc['source']}]\n{doc['text']}\n")
        if doc.get("url"):
            references.append({
                "num": i,
                "source": doc["source"],
                "url": doc["url"],
            })

    context_str = "\n".join(parts)
    return context_str, references
