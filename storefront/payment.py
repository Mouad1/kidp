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
    def create_checkout(self, amount: int, currency: str, reference: str) -> CheckoutSession: ...


class StubPaymentProvider:
    """No real charge. Returns a pending session pointing at an internal mock page."""

    def create_checkout(self, amount: int, currency: str, reference: str) -> CheckoutSession:
        return CheckoutSession(
            reference=reference, amount=amount, currency=currency,
            status="pending", url=f"/store/checkout/mock/{reference}",
        )


def get_payment_provider(settings: dict) -> PaymentProvider:
    provider = (settings or {}).get("payment_provider", "stub")
    if provider == "stub":
        return StubPaymentProvider()
    raise ValueError(f"Unsupported payment provider: {provider!r}")
