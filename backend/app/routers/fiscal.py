from fastapi import APIRouter
from datetime import datetime, date
from app.services.analysis_service import (
    get_trimestre_actual,
    dias_hasta_proxima_declaracion,
    PLAZOS_TRIMESTRALES,
)
from app.services.knowledge_base import MODELOS_FISCALES

router = APIRouter()


@router.get("/calendar")
def get_fiscal_calendar():
    """Devuelve el calendario fiscal del año con los próximos plazos."""
    hoy = datetime.now()
    año = hoy.year
    trimestre_actual = get_trimestre_actual()
    dias_restantes = dias_hasta_proxima_declaracion()

    plazos = []
    fechas_plazos = {
        1: date(año, 4, 20),
        2: date(año, 7, 20),
        3: date(año, 10, 20),
        4: date(año + 1, 1, 30),
    }

    for t, fecha in fechas_plazos.items():
        plazo_info = PLAZOS_TRIMESTRALES[t]
        estado = "pasado" if fecha < hoy.date() else ("proximo" if t == trimestre_actual else "futuro")
        plazos.append({
            "trimestre": t,
            "fecha": fecha.isoformat(),
            "modelos": plazo_info["modelos"],
            "estado": estado,
            "dias_restantes": (fecha - hoy.date()).days if fecha >= hoy.date() else None,
        })

    return {
        "fecha_actual": hoy.date().isoformat(),
        "trimestre_actual": trimestre_actual,
        "dias_proxima_declaracion": dias_restantes,
        "plazos": plazos,
        "modelos_info": {m: MODELOS_FISCALES[m] for m in ["130", "303", "390", "347", "100"]},
    }


@router.get("/deductions")
def get_deductions_guide():
    """Guía completa de gastos deducibles."""
    from app.services.knowledge_base import GASTOS_DEDUCIBLES
    return {
        "gastos_deducibles": GASTOS_DEDUCIBLES,
        "nota": "Los porcentajes son orientativos. Consulta con tu asesor fiscal para tu caso concreto.",
        "fuente": "AEAT — Normativa IRPF e IVA 2024-2025",
    }


@router.get("/iva-types")
def get_iva_types():
    """Información sobre tipos de IVA aplicables en España."""
    from app.services.knowledge_base import TIPOS_IVA_INFO
    return TIPOS_IVA_INFO
