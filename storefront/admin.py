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


def list_admins(db: Database) -> list[dict]:
    rows = db.query_all("SELECT email, created_at FROM admins ORDER BY created_at ASC")
    return [{"email": row["email"], "created_at": row["created_at"]} for row in rows]


def remove_admin(db: Database, email: str) -> None:
    normalized = (email or "").strip().lower()
    if normalized:
        db.execute("DELETE FROM admins WHERE email = ?", (normalized,))
