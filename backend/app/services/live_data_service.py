"""
FiscalIA — Servicio de datos en tiempo real
Raspa fuentes oficiales españolas según el tema detectado en la pregunta.
Sin API keys. Sin base de datos. Cache en memoria con TTL configurable.

Fuentes por tema:
  jubilación / pensión  → seg-social.es (tabla de edades actualizada)
  autónomos / cuotas    → seg-social.es (tablas RETA)
  IVA / IRPF / IS       → agenciatributaria.gob.es
  SMI                   → mitramiss.gob.es / BOE
  novedades generales   → boe.es RSS
"""

import re
import httpx
from datetime import datetime, timedelta
from typing import Optional

# ── Cache ─────────────────────────────────────────────────────
_cache: dict = {}
CACHE_TTL = timedelta(hours=24)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def _fresh(key: str) -> bool:
    e = _cache.get(key)
    return bool(e and datetime.utcnow() - e["at"] < CACHE_TTL)


def _get(key: str) -> str:
    return _cache.get(key, {}).get("text", "")


def _set(key: str, text: str):
    _cache[key] = {"text": text, "at": datetime.utcnow()}


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# ── Scrapers por tema ─────────────────────────────────────────

async def _fetch_url(url: str) -> str:
    """Descarga una URL y devuelve el texto limpio. Falla silenciosamente."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http:
            r = await http.get(url, headers=HEADERS)
            if r.status_code == 200:
                return _strip_html(r.text)
    except Exception:
        pass
    return ""


def _extract_around(text: str, keywords: list[str], window: int = 800) -> str:
    """Extrae el fragmento de texto más relevante alrededor de las keywords."""
    tl = text.lower()
    best_pos = -1
    best_count = 0

    for kw in keywords:
        pos = tl.find(kw.lower())
        if pos > 0:
            # Contar cuántas keywords aparecen cerca de esta posición
            snippet = tl[max(0, pos-100):pos+window]
            count = sum(1 for k in keywords if k.lower() in snippet)
            if count > best_count:
                best_count = count
                best_pos = pos

    if best_pos < 0:
        return text[:window]

    start = max(0, best_pos - 100)
    return text[start:start + window]


async def fetch_jubilacion_data() -> str:
    """Raspa la tabla oficial de edades de jubilación del INSS."""
    KEY = "jubilacion"
    if _fresh(KEY):
        return _get(KEY)

    URLS = [
        # Página principal de jubilación ordinaria del INSS
        "https://www.seg-social.es/wps/portal/wss/internet/Trabajadores/PrestacionesPensionesContributivas/pensiones/jubilacion/requisitosGenerales",
        # Página de jubilación activa
        "https://www.seg-social.es/wps/portal/wss/internet/Trabajadores/PrestacionesPensionesContributivas/pensiones/jubilacion/jubilacionActiva",
    ]

    results = []
    for url in URLS:
        text = await _fetch_url(url)
        if text:
            snippet = _extract_around(text, [
                "2026", "edad", "años cotizados", "38 años", "67", "66", "65",
                "jubilación activa", "ordinaria", "meses"
            ])
            if snippet:
                results.append(f"[Fuente: {url}]\n{snippet}")

    combined = "\n\n".join(results) if results else ""
    _set(KEY, combined)
    return combined


async def fetch_autonomos_cuotas() -> str:
    """Raspa las tablas de cotización de autónomos (RETA) del año vigente."""
    KEY = "autonomos_cuotas"
    if _fresh(KEY):
        return _get(KEY)

    URLS = [
        "https://www.seg-social.es/wps/portal/wss/internet/Trabajadores/Afiliacion/10774/10787",
        "https://www.seg-social.es/wps/portal/wss/internet/Trabajadores/TrabajoAutonomo",
    ]

    results = []
    for url in URLS:
        text = await _fetch_url(url)
        if text:
            snippet = _extract_around(text, [
                "2026", "cuota", "cotización", "tramo", "rendimiento", "€/mes",
                "tarifa plana", "80", "ingresos reales"
            ])
            if snippet:
                results.append(f"[Fuente: {url}]\n{snippet}")

    combined = "\n\n".join(results) if results else ""
    _set(KEY, combined)
    return combined


async def fetch_irpf_data() -> str:
    """Raspa los tramos IRPF y retenciones vigentes de la AEAT."""
    KEY = "irpf"
    if _fresh(KEY):
        return _get(KEY)

    text = await _fetch_url("https://sede.agenciatributaria.gob.es/Sede/irpf.html")
    snippet = _extract_around(text, ["2026", "tramo", "tipo", "19%", "24%", "30%", "retención", "130"])
    _set(KEY, snippet)
    return snippet


async def fetch_iva_data() -> str:
    """Raspa tipos de IVA vigentes de la AEAT."""
    KEY = "iva"
    if _fresh(KEY):
        return _get(KEY)

    text = await _fetch_url("https://sede.agenciatributaria.gob.es/Sede/iva.html")
    snippet = _extract_around(text, ["2026", "21%", "10%", "4%", "tipo", "general", "reducido"])
    _set(KEY, snippet)
    return snippet


async def fetch_smi_data() -> str:
    """Raspa el SMI vigente del Ministerio de Trabajo."""
    KEY = "smi"
    if _fresh(KEY):
        return _get(KEY)

    URLS = [
        "https://www.mites.gob.es/es/guia/texto/guia_8/contenidos/guia_8_9_1.htm",
        "https://www.boe.es/boe/dias/2026/01/01/",  # BOE 1 enero — suele publicarse el SMI
    ]

    for url in URLS:
        text = await _fetch_url(url)
        if text:
            snippet = _extract_around(text, ["salario mínimo", "SMI", "2026", "€/día", "€/mes", "1.1"])
            if snippet:
                _set(KEY, snippet)
                return snippet

    _set(KEY, "")
    return ""


async def fetch_pensiones_data() -> str:
    """Raspa datos de pensiones contributivas (cuantías, revalorización) del INSS."""
    KEY = "pensiones"
    if _fresh(KEY):
        return _get(KEY)

    text = await _fetch_url(
        "https://www.seg-social.es/wps/portal/wss/internet/Pensionistas/Jubilados/10694"
    )
    snippet = _extract_around(text, [
        "2026", "revalorización", "pensión máxima", "pensión mínima",
        "jubilación activa", "50%", "cuantía"
    ])
    _set(KEY, snippet)
    return snippet


# ── Router: detecta el tema y llama al scraper adecuado ───────

TOPIC_MAP = [
    (["jubilación activa", "jubilacion activa", "jubilarse activo",
      "trabajar jubilado", "pensión y trabajar"], fetch_jubilacion_data),

    (["jubilación", "jubilacion", "pensión", "pension", "edad jubilarse",
      "años para jubilar", "cuándo me jubilo", "cuando me jubilo",
      "jubilación ordinaria", "jubilación anticipada"], fetch_jubilacion_data),

    (["cuota autónomo", "cuota autonomo", "cotización autónomo", "reta",
      "tarifa plana", "cuánto pago de autónomo", "tramos autónomos",
      "ingresos reales"], fetch_autonomos_cuotas),

    (["irpf", "renta", "tramo", "retención", "pago fraccionado",
      "modelo 130", "estimación directa"], fetch_irpf_data),

    (["iva", "tipo iva", "21%", "10%", "4%", "modelo 303"], fetch_iva_data),

    (["smi", "salario mínimo", "salario minimo", "iprem"], fetch_smi_data),

    (["pensión mínima", "pension minima", "revalorización",
      "cuantía pensión", "pensión máxima"], fetch_pensiones_data),
]


async def get_live_data_for_question(question: str) -> str:
    """
    Detecta el tema de la pregunta y raspa la fuente oficial correspondiente.
    Devuelve texto fresco de la web o cadena vacía si no aplica / falla.
    """
    q = question.lower()

    matched_fetchers = []
    for keywords, fetcher in TOPIC_MAP:
        if any(kw in q for kw in keywords):
            if fetcher not in matched_fetchers:
                matched_fetchers.append(fetcher)

    if not matched_fetchers:
        return ""

    # Ejecutar los fetchers relevantes (normalmente 1-2)
    import asyncio
    results = await asyncio.gather(*[f() for f in matched_fetchers], return_exceptions=True)

    parts = [r for r in results if isinstance(r, str) and r.strip()]
    return "\n\n".join(parts)
