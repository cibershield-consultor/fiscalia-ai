"""
Fiscalía IA — Sistema de planes Freemium / Premium
"""

PLANS = {
    "free": {
        "name": "Gratuito",
        "price_monthly": 0,
        "messages_per_day": 10,
        "model": "llama-3.3-70b-versatile",   # Groq free
        "features": [
            "10 preguntas/día al asesor fiscal",
            "Historial últimas 5 conversaciones",
            "Acceso a conocimiento fiscal básico",
            "Análisis de hasta 3 facturas/mes",
        ],
        "limits": {
            "max_conversations": 5,
            "max_invoices_month": 3,
            "file_upload": False,
            "image_analysis": False,
            "dashboard": False,
            "export": False,
        }
    },
    "premium": {
        "name": "Premium",
        "price_monthly": 9.99,
        "price_yearly": 7.99,   # per month if paid yearly
        "messages_per_day": 999,  # unlimited
        "model": "llama-3.3-70b-versatile",
        "features": [
            "Preguntas ilimitadas al asesor fiscal",
            "Historial completo de conversaciones",
            "Subida de facturas PDF e imágenes",
            "Análisis IA de documentos fiscales",
            "Dashboard financiero completo",
            "Cálculo automático IVA/IRPF",
            "Exportación de informes",
            "Conocimiento fiscal actualizado 2026",
            "Alertas de plazos fiscales",
            "Soporte prioritario",
        ],
        "limits": {
            "max_conversations": 9999,
            "max_invoices_month": 9999,
            "file_upload": True,
            "image_analysis": True,
            "dashboard": True,
            "export": True,
        }
    }
}


def get_plan(plan_name: str) -> dict:
    return PLANS.get(plan_name, PLANS["free"])


def can_send_message(user) -> tuple[bool, str]:
    """Check if user can send a message based on their plan."""
    from datetime import datetime
    plan = get_plan(user.plan)

    # Reset daily counter if needed
    now = datetime.utcnow()
    if user.messages_reset_at and (now - user.messages_reset_at).days >= 1:
        return True, ""  # Will be reset in router

    limit = plan["messages_per_day"]
    if limit == 999:
        return True, ""

    if user.messages_today >= limit:
        return False, f"Has alcanzado el límite de {limit} preguntas diarias del plan gratuito. Actualiza a Premium para preguntas ilimitadas."

    return True, ""


def can_upload_files(user) -> bool:
    plan = get_plan(user.plan)
    return plan["limits"]["file_upload"]


def can_access_dashboard(user) -> bool:
    plan = get_plan(user.plan)
    return plan["limits"]["dashboard"]
