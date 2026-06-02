import datetime as dt
from storefront.db import (
    Database, new_reference, create_order, get_order, set_order_status, list_orders,
)
from storefront.auth import SqliteAuthStore, request_code, verify_code, FakeCodeSender


def _db(tmp_path):
    return Database(tmp_path / "storefront.db")


def test_migrations_are_idempotent(tmp_path):
    Database(tmp_path / "s.db")
    db = Database(tmp_path / "s.db")  # second open must not fail
    assert db.query_all("SELECT name FROM sqlite_master WHERE type='table'")


def test_order_crud(tmp_path):
    db = _db(tmp_path)
    now = dt.datetime(2026, 6, 2, 10, 0, 0)
    ref = new_reference("alpha")
    create_order(db, reference=ref, slug="alpha", email="a@b.com",
                 child_name="Lina", photo_path="/x/photo.png", page_count=12,
                 amount_cents=530, currency="USD", now=now)
    order = get_order(db, ref)
    assert order["status"] == "pending"
    assert order["child_name"] == "Lina"
    assert order["amount_cents"] == 530
    set_order_status(db, ref, "paid", now=now)
    assert get_order(db, ref)["status"] == "paid"
    assert get_order(db, "missing") is None


def test_set_status_rejects_unknown(tmp_path):
    db = _db(tmp_path)
    now = dt.datetime(2026, 6, 2, 10, 0, 0)
    ref = new_reference("alpha")
    create_order(db, reference=ref, slug="alpha", email="a@b.com",
                 child_name="Lina", photo_path="/x/photo.png", page_count=12,
                 amount_cents=530, currency="USD", now=now)
    import pytest
    with pytest.raises(ValueError):
        set_order_status(db, ref, "weird", now=now)


def test_list_orders_newest_first(tmp_path):
    db = _db(tmp_path)
    base = dt.datetime(2026, 6, 2, 10, 0, 0)
    for i in range(3):
        create_order(db, reference=f"r{i}", slug="alpha", email="a@b.com",
                     child_name=f"K{i}", photo_path="/x.png", page_count=8,
                     amount_cents=100, currency="USD",
                     now=base + dt.timedelta(minutes=i))
    refs = [o["reference"] for o in list_orders(db)]
    assert refs == ["r2", "r1", "r0"]


def test_sqlite_auth_store_roundtrip_and_rate_limit(tmp_path):
    db = _db(tmp_path)
    store = SqliteAuthStore(db)
    sender = FakeCodeSender()
    now = dt.datetime(2026, 6, 2, 12, 0, 0)
    request_code("a@b.com", now=now, code_sender=sender, store=store)
    code = sender.sent[0][1]
    for _ in range(5):
        assert not verify_code("a@b.com", "000000", now=now, store=store)
    assert not verify_code("a@b.com", code, now=now, store=store)


def test_sqlite_auth_store_success(tmp_path):
    db = _db(tmp_path)
    store = SqliteAuthStore(db)
    sender = FakeCodeSender()
    now = dt.datetime(2026, 6, 2, 12, 0, 0)
    request_code("a@b.com", now=now, code_sender=sender, store=store)
    code = sender.sent[0][1]
    assert verify_code("a@b.com", code, now=now + dt.timedelta(seconds=10), store=store)
