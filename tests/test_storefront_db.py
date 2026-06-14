import datetime as dt
from storefront.db import (
    Database, new_reference, create_order, get_order, set_order_status, list_orders,
    set_order_notes, get_stats,
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


def test_set_order_notes(tmp_path):
    db = _db(tmp_path)
    now = dt.datetime(2026, 6, 7, 9, 0, 0)
    ref = new_reference("alpha")
    create_order(db, reference=ref, slug="alpha", email="a@b.com",
                 child_name="Lina", photo_path="/x.png", page_count=8,
                 amount_cents=320, currency="USD", now=now)
    set_order_notes(db, ref, "  shipped via Colissimo  ", now=now)
    assert get_order(db, ref)["notes"] == "shipped via Colissimo"


def test_get_stats_empty(tmp_path):
    db = _db(tmp_path)
    s = get_stats(db, today="2026-06-07", month_prefix="2026-06")
    assert s["revenue_today_cents"] == 0
    assert s["revenue_month_cents"] == 0
    assert s["pending_count"] == 0


def test_get_stats_counts_correctly(tmp_path):
    db = _db(tmp_path)
    today = dt.datetime(2026, 6, 7, 10, 0, 0)
    yesterday = dt.datetime(2026, 6, 6, 10, 0, 0)
    # paid today
    r1 = new_reference("a"); create_order(db, reference=r1, slug="a", email="x@y.com",
        child_name="A", photo_path="/p", page_count=8, amount_cents=500, currency="USD", now=today)
    set_order_status(db, r1, "paid", now=today)
    # paid yesterday (different day, same month)
    r2 = new_reference("a"); create_order(db, reference=r2, slug="a", email="x@y.com",
        child_name="B", photo_path="/p", page_count=8, amount_cents=300, currency="USD", now=yesterday)
    set_order_status(db, r2, "paid", now=yesterday)
    # pending today
    r3 = new_reference("a"); create_order(db, reference=r3, slug="a", email="x@y.com",
        child_name="C", photo_path="/p", page_count=8, amount_cents=200, currency="USD", now=today)
    s = get_stats(db, today="2026-06-07", month_prefix="2026-06")
    assert s["revenue_today_cents"] == 500
    assert s["revenue_month_cents"] == 800  # 500 + 300
    assert s["pending_count"] == 1


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
