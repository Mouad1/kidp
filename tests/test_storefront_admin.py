import datetime as dt
from storefront.db import Database
from storefront.admin import seed_admins, is_admin


def test_seed_and_check_admin(tmp_path):
    db = Database(tmp_path / "s.db")
    now = dt.datetime(2026, 6, 2, 10, 0, 0)
    seed_admins(db, ["You@Example.com", "collab@example.com"], now=now)
    assert is_admin(db, "you@example.com") is True
    assert is_admin(db, "COLLAB@example.com") is True
    assert is_admin(db, "stranger@example.com") is False


def test_seed_is_idempotent(tmp_path):
    db = Database(tmp_path / "s.db")
    now = dt.datetime(2026, 6, 2, 10, 0, 0)
    seed_admins(db, ["a@b.com"], now=now)
    seed_admins(db, ["a@b.com"], now=now)
    assert is_admin(db, "a@b.com") is True


def test_blank_emails_ignored(tmp_path):
    db = Database(tmp_path / "s.db")
    now = dt.datetime(2026, 6, 2, 10, 0, 0)
    seed_admins(db, ["", "  "], now=now)
    assert is_admin(db, "") is False
