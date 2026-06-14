import os
from dataclasses import dataclass
from typing import Protocol


@dataclass
class CheckoutSession:
    reference: str
    amount: int  # minor units (cents)
    currency: str
    status: str  # "pending" | "paid" | "failed"
    url: str


class PaymentProvider(Protocol):
    def create_checkout(self, amount: int, currency: str, reference: str,
                        success_url: str = "", cancel_url: str = "",
                        customer_email: str = "") -> CheckoutSession: ...


class StubPaymentProvider:
    """No real charge. Settles immediately — for local dev without Stripe keys."""

    def create_checkout(self, amount: int, currency: str, reference: str,
                        success_url: str = "", cancel_url: str = "") -> CheckoutSession:
        return CheckoutSession(
            reference=reference, amount=amount, currency=currency,
            status="paid", url=success_url or f"/store/success?reference={reference}",
        )


class StripePaymentProvider:
    """Stripe Checkout (hosted). Order stays pending until webhook confirms payment."""

    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key

    def create_checkout(self, amount: int, currency: str, reference: str,
                        success_url: str = "", cancel_url: str = "",
                        customer_email: str = "") -> CheckoutSession:
        import stripe
        stripe.api_key = self.secret_key
        stripe.api_version = "2026-05-27.dahlia"
        params: dict = dict(
            mode="payment",
            client_reference_id=reference,
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": f"Personalized Book — {reference}"},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        if customer_email:
            params["customer_email"] = customer_email
        session = stripe.checkout.Session.create(**params)
        return CheckoutSession(
            reference=reference, amount=amount, currency=currency,
            status="pending", url=session.url,
        )


def get_payment_provider(settings: dict) -> PaymentProvider:
    provider = (settings or {}).get("payment_provider", "stub")
    if provider == "stub":
        return StubPaymentProvider()
    if provider == "stripe":
        secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
        if not secret_key:
            raise RuntimeError(
                "STRIPE_SECRET_KEY env var is required when payment_provider is 'stripe'"
            )
        return StripePaymentProvider(secret_key=secret_key)
    raise ValueError(f"Unsupported payment provider: {provider!r}")
