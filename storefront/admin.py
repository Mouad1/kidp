import datetime as dt

from storefront.db import Database


def seed_admins(db: Database, emails: list[str], now: dt.datetime) -> None:
    iso = now.isoformat()
    for email in emails:
        normalized = (email or "").strip().lower()
        if not normalized:
            continue
        db.execute(
            "INSERT INTO admins (email, created_at) VALUES (?, ?) "
            "ON CONFLICT(email) DO NOTHING",
            (normalized, iso),
        )


def is_admin(db: Database, email: str) -> bool:
    normalized = (email or "").strip().lower()
    if not normalized:
        return False
    row = db.query_one("SELECT email FROM admins WHERE email = ?", (normalized,))
    return row is not None
