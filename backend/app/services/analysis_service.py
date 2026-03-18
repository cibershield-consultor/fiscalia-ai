"""
Fiscalía IA — Motor de Análisis Financiero
Cálculos fiscales para autónomos españoles 2024-2025
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


# ── Constantes fiscales 2024-2025 ──────────────────────────────

TRAMOS_IRPF_2024 = [
    (12_450,   0.19),
    (7_750,    0.24),   # hasta 20.200
    (15_000,   0.30),   # hasta 35.200
    (24_800,   0.37),   # hasta 60.000
    (240_000,  0.45),   # hasta 300.000
]
TIPO_MARGINAL_MAXIMO = 0.47

TIPOS_IVA = {
    "general":       0.21,
    "reducido":      0.10,
    "superreducido": 0.04,
    "exento":        0.00,
}

CUOTA_AUTONOMO_TRAMOS_2024 = [
    (670,   200),
    (900,   220),
    (1_166, 260),
    (1_300, 280),
    (1_500, 294),
    (1_700, 294),
    (1_850, 350),
    (2_030, 370),
    (2_330, 390),
    (2_760, 420),
    (3_190, 460),
    (3_620, 480),
    (4_050, 500),
    (6_000, 530),
    (float("inf"), 590),
]

TARIFA_PLANA = 80.0          # €/mes durante los primeros 12 meses
RETENCION_GENERAL = 0.15     # 15% retención IRPF
RETENCION_INICIO  = 0.07     # 7% retención 2 primeros años

PLAZOS_TRIMESTRALES = {
    1: {"inicio": "01/04", "fin": "20/04", "modelos": ["130", "303"]},
    2: {"inicio": "01/07", "fin": "20/07", "modelos": ["130", "303"]},
    3: {"inicio": "01/10", "fin": "20/10", "modelos": ["130", "303"]},
    4: {"inicio": "01/01", "fin": "30/01", "modelos": ["130", "303", "390", "190"]},
}


# ── Cálculos ────────────────────────────────────────────────────

def calcular_irpf(base_liquidable: float) -> float:
    """Calcula el IRPF estatal + autonómico (media) para 2024."""
    if base_liquidable <= 0:
        return 0.0

    impuesto = 0.0
    restante = base_liquidable

    for limite, tipo in TRAMOS_IRPF_2024:
        if restante <= 0:
            break
        gravable = min(restante, limite)
        impuesto += gravable * tipo
        restante -= gravable

    if restante > 0:
        impuesto += restante * TIPO_MARGINAL_MAXIMO

    return round(impuesto, 2)


def calcular_tipo_efectivo(base: float) -> float:
    """Devuelve el tipo efectivo de IRPF en porcentaje."""
    if base <= 0:
        return 0.0
    impuesto = calcular_irpf(base)
    return round(impuesto / base * 100, 2)


def calcular_iva(base: float, tipo: str = "general") -> dict:
    """Calcula IVA repercutido o soportado."""
    tasa = TIPOS_IVA.get(tipo, 0.21)
    cuota = round(base * tasa, 2)
    return {
        "base": base,
        "tipo": tipo,
        "tasa": tasa,
        "cuota": cuota,
        "total": round(base + cuota, 2),
    }


def calcular_cuota_autonomo(ingresos_netos_mensuales: float) -> float:
    """Calcula la cuota mensual de autónomo según ingresos reales (sistema 2023+)."""
    for tope, cuota in CUOTA_AUTONOMO_TRAMOS_2024:
        if ingresos_netos_mensuales <= tope:
            return cuota
    return CUOTA_AUTONOMO_TRAMOS_2024[-1][1]


def calcular_pago_fraccionado_130(
    ingresos: float,
    gastos_deducibles: float,
    retenciones_soportadas: float,
    pagos_previos: float = 0.0,
) -> float:
    """
    Calcula el pago fraccionado del Modelo 130 (IRPF trimestral).
    El resultado es el 20% del rendimiento neto menos retenciones y pagos previos.
    """
    rendimiento_neto = max(0, ingresos - gastos_deducibles)
    pago = rendimiento_neto * 0.20
    pago -= retenciones_soportadas
    pago -= pagos_previos
    return max(0, round(pago, 2))


@dataclass
class ResumenFiscalTrimestral:
    trimestre: int
    año: int
    ingresos: float
    gastos: float
    gastos_deducibles: float
    beneficio: float
    margen_pct: float
    iva_repercutido: float
    iva_soportado: float
    iva_a_pagar: float
    irpf_retenido: float
    irpf_estimado_anual: float
    modelo_130: float
    tipo_efectivo_irpf: float
    cuota_autonomo_estimada: float
    plazo_declaracion: str
    alerta: Optional[str] = None


def generar_resumen_trimestral(
    trimestre: int,
    año: int,
    ingresos: float,
    gastos: float,
    gastos_deducibles: float,
    retenciones_soportadas: float = 0.0,
    pagos_previos: float = 0.0,
) -> ResumenFiscalTrimestral:
    """Genera el resumen fiscal completo de un trimestre."""
    beneficio = ingresos - gastos
    margen = (beneficio / ingresos * 100) if ingresos > 0 else 0

    iva_repercutido = ingresos * TIPOS_IVA["general"]
    iva_soportado = gastos_deducibles * TIPOS_IVA["general"]
    iva_a_pagar = max(0, iva_repercutido - iva_soportado)

    irpf_retenido = retenciones_soportadas or (ingresos * RETENCION_GENERAL)
    base_irpf = ingresos - gastos_deducibles
    irpf_estimado_anual = calcular_irpf(base_irpf * 4)  # proyección anual
    tipo_efectivo = calcular_tipo_efectivo(base_irpf * 4)

    modelo_130 = calcular_pago_fraccionado_130(
        ingresos, gastos_deducibles, retenciones_soportadas, pagos_previos
    )

    # Cuota autónomo estimada (ingresos netos mensuales)
    ingresos_mensuales = (ingresos - gastos) / 3
    cuota_autonomo = calcular_cuota_autonomo(ingresos_mensuales)

    plazo = PLAZOS_TRIMESTRALES.get(trimestre, {})
    plazo_str = f"{plazo.get('fin', '—')} (Modelos: {', '.join(plazo.get('modelos', []))})"

    # Alertas
    alerta = None
    if margen < 0:
        alerta = "⚠️ Resultado negativo: estás perdiendo dinero este trimestre"
    elif margen < 20:
        alerta = "📉 Margen bajo (<20%): revisa si puedes reducir gastos no esenciales"
    elif iva_a_pagar > ingresos * 0.25:
        alerta = "🏦 IVA elevado: asegúrate de tener liquidez para la declaración"

    return ResumenFiscalTrimestral(
        trimestre=trimestre,
        año=año,
        ingresos=round(ingresos, 2),
        gastos=round(gastos, 2),
        gastos_deducibles=round(gastos_deducibles, 2),
        beneficio=round(beneficio, 2),
        margen_pct=round(margen, 2),
        iva_repercutido=round(iva_repercutido, 2),
        iva_soportado=round(iva_soportado, 2),
        iva_a_pagar=round(iva_a_pagar, 2),
        irpf_retenido=round(irpf_retenido, 2),
        irpf_estimado_anual=round(irpf_estimado_anual, 2),
        modelo_130=modelo_130,
        tipo_efectivo_irpf=tipo_efectivo,
        cuota_autonomo_estimada=cuota_autonomo,
        plazo_declaracion=plazo_str,
        alerta=alerta,
    )


def get_trimestre_actual() -> int:
    return (datetime.now().month - 1) // 3 + 1


def dias_hasta_proxima_declaracion() -> int:
    """Calcula los días que quedan para la próxima declaración trimestral."""
    hoy = datetime.now()
    año = hoy.year
    q = get_trimestre_actual()

    plazos_fechas = {
        1: datetime(año, 4, 20),
        2: datetime(año, 7, 20),
        3: datetime(año, 10, 20),
        4: datetime(año + 1, 1, 30),
    }

    # Buscar la próxima fecha de plazo que no haya pasado
    for t in [q, (q % 4) + 1]:
        fecha = plazos_fechas.get(t)
        if fecha and fecha > hoy:
            return (fecha - hoy).days

    return 0
