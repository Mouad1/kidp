from storefront.payment import StubPaymentProvider, CheckoutSession, get_payment_provider


def test_stub_provider_creates_pending_session():
    p = StubPaymentProvider()
    s = p.create_checkout(amount=530, currency="USD", reference="order-1")
    assert isinstance(s, CheckoutSession)
    assert s.status == "pending"
    assert s.amount == 530
    assert s.reference == "order-1"
    assert s.url.endswith("order-1")


def test_factory_defaults_to_stub():
    p = get_payment_provider({"payment_provider": "stub"})
    assert isinstance(p, StubPaymentProvider)


def test_settings_example_has_storefront_block():
    import json, pathlib
    root = pathlib.Path(__file__).parent.parent
    data = json.loads((root / "settings.example.json").read_text())
    assert "storefront" in data
    sf = data["storefront"]
    for key in ("session_secret", "payment_provider", "smtp"):
        assert key in sf
