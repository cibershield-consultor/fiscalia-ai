"""
Fiscalía IA — Integración con Stripe
Pagos recurrentes mensuales para el plan Premium
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import json
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

router = APIRouter()

# Precio mensual Premium en Stripe (crear en dashboard.stripe.com)
STRIPE_PRICE_ID = "price_XXXXXXXXXXXXXXXX"  # Reemplazar con tu Price ID de Stripe


class CreateCheckoutRequest(BaseModel):
    user_id: int
    success_url: str
    cancel_url: str


@router.post("/create-checkout")
async def create_checkout(req: CreateCheckoutRequest, db: AsyncSession = Depends(get_db)):
    """
    Crea una sesión de pago de Stripe.
    El frontend redirige al usuario a la URL devuelta.
    """
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        result = await db.execute(select(User).where(User.id == req.user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            customer_email=user.email,
            client_reference_id=str(user.id),
            success_url=req.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=req.cancel_url,
            metadata={"user_id": str(user.id)},
        )

        return JSONResponse(content={"checkout_url": session.url, "session_id": session.id})

    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe no instalado. Añade 'stripe' a requirements.txt")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None), db: AsyncSession = Depends(get_db)):
    """
    Webhook de Stripe — Stripe llama aquí automáticamente cuando hay un pago.
    Configurar en: dashboard.stripe.com → Developers → Webhooks
    URL: https://fiscalia-backend.onrender.com/api/stripe/webhook
    Eventos a escuchar: checkout.session.completed, customer.subscription.deleted
    """
    payload = await request.body()

    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    # ── Pago completado → activar Premium ──
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session.get("client_reference_id") or session["metadata"].get("user_id", 0))

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.plan = "premium"
            user.plan_expires_at = None
            user.stripe_customer_id = session.get("customer")
            await db.commit()

    # ── Suscripción cancelada → volver a free ──
    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.paused"):
        customer_id = event["data"]["object"]["customer"]
        result = await db.execute(select(User).where(User.stripe_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user:
            user.plan = "free"
            await db.commit()

    return JSONResponse(content={"received": True})


@router.post("/cancel-subscription")
async def cancel_subscription(user_id: int, db: AsyncSession = Depends(get_db)):
    """Cancela la suscripción activa del usuario en Stripe."""
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not getattr(user, 'stripe_customer_id', None):
            raise HTTPException(status_code=404, detail="Suscripción no encontrada")

        subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id, status="active")
        for sub in subscriptions.data:
            stripe.Subscription.cancel(sub.id)

        return JSONResponse(content={"ok": True, "message": "Suscripción cancelada. Seguirás con Premium hasta el final del período."})

    except ImportError:
        raise HTTPException(status_code=500, detail="Stripe no instalado")
