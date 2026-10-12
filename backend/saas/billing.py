"""
Achat de packs de crédits par Stripe Checkout.

1. POST /api/app/checkout crée une session Checkout (prix du pack en euros, TTC) et un Purchase
   « pending » ; le navigateur part sur la page de paiement de Stripe.
2. Stripe appelle POST /api/stripe/webhook (checkout.session.completed). Le webhook seul crédite :
   le retour du navigateur sur /app/credits?paid=1 ne prouve rien.
3. Le crédit est idempotent (Purchase.status) : un webhook rejoué ne crédite pas deux fois.
"""
from decimal import Decimal

from django.db import transaction

from ..config.settings import settings
from ..utils.logging import logger
from . import credits, pricing
from .models import Purchase, Workspace


class BillingDisabled(Exception):
    pass


def enabled() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def _stripe():
    if not enabled():
        raise BillingDisabled("Les paiements ne sont pas encore activés.")
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout(workspace: Workspace, email: str, pack_id: str, frontend_url: str) -> str:
    pack = pricing.PACKS_BY_ID.get(pack_id)
    if pack is None:
        raise ValueError(f"Pack inconnu : {pack_id}")
    stripe = _stripe()
    price_data = {
        "currency": "eur",
        "unit_amount": pack["price_eur"] * 100,
        "product_data": {"name": f"{pack['credits']:,} crédits".replace(",", " ")},
    }
    params = {}
    if settings.STRIPE_AUTOMATIC_TAX:
        price_data["tax_behavior"] = "inclusive"  # prix affichés TTC
        params["automatic_tax"] = {"enabled": True}
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price_data": price_data, "quantity": 1}],
        customer_email=email,
        client_reference_id=str(workspace.id),
        metadata={"workspace_id": str(workspace.id), "pack": pack_id},
        success_url=f"{frontend_url}/app/credits?paid=1",
        cancel_url=f"{frontend_url}/app/credits",
        **params,
    )
    Purchase.objects.create(workspace=workspace, pack=pack_id, price_eur=Decimal(pack["price_eur"]),
                            credits=pack["credits"], stripe_session_id=session.id)
    return session.url


def handle_webhook(payload: bytes, signature: str) -> None:
    """Vérifie la signature Stripe et crédite un paiement réussi. Lève ValueError si invalide."""
    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise ValueError(f"Webhook Stripe invalide : {e}") from e
    if event["type"] not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        return
    session = event["data"]["object"]
    if session.get("payment_status") != "paid":
        return
    fulfill(session["id"])


def fulfill(session_id: str) -> bool:
    """Crédite l'achat une seule fois. Renvoie True si des crédits ont été ajoutés."""
    with transaction.atomic():
        purchase = Purchase.objects.select_for_update().filter(stripe_session_id=session_id).first()
        if purchase is None:
            logger.error(f"Stripe : session {session_id} sans achat correspondant")
            return False
        if purchase.status == "paid":
            return False
        purchase.status = "paid"
        purchase.save(update_fields=["status"])
        credits.credit(purchase.workspace, purchase.credits, "purchase",
                       f"Pack de {purchase.price_eur:.0f} €", reference=session_id)
        Workspace.objects.filter(pk=purchase.workspace_id).update(plan="paid")
    logger.info(f"Stripe : {purchase.credits} crédits ajoutés à {purchase.workspace.tenant_id}")
    return True
