import datetime as dt
import pathlib
import sqlite3
import threading
import secrets

_DEF_STATUS = "pending"
_VALID_STATUS = ("pending", "paid", "failed")


class Database:
    """Thin SQLite wrapper with idempotent migrations. Stdlib only."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    reference    TEXT PRIMARY KEY,
                    slug         TEXT NOT NULL,
                    email        TEXT NOT NULL,
                    child_name   TEXT NOT NULL,
                    photo_path   TEXT NOT NULL,
                    page_count   INTEGER NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    currency     TEXT NOT NULL,
                    status       TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auth_codes (
                    email      TEXT PRIMARY KEY,
                    code_hash  TEXT NOT NULL,
                    salt       TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    attempts   INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS admins (
                    email      TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self._conn.close()


def new_reference(slug: str) -> str:
    return f"{slug}-{secrets.token_hex(6)}"


def create_order(db: Database, *, reference: str, slug: str, email: str,
                 child_name: str, photo_path: str, page_count: int,
                 amount_cents: int, currency: str, now: dt.datetime,
                 status: str = _DEF_STATUS) -> str:
    iso = now.isoformat()
    db.execute(
        "INSERT INTO orders (reference, slug, email, child_name, photo_path, "
        "page_count, amount_cents, currency, status, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (reference, slug, email, child_name, photo_path, page_count,
         amount_cents, currency, status, iso, iso),
    )
    return reference


def get_order(db: Database, reference: str) -> dict | None:
    row = db.query_one("SELECT * FROM orders WHERE reference = ?", (reference,))
    return dict(row) if row else None


def set_order_status(db: Database, reference: str, status: str,
                     now: dt.datetime) -> None:
    if status not in _VALID_STATUS:
        raise ValueError(f"Invalid order status: {status!r}")
    db.execute(
        "UPDATE orders SET status = ?, updated_at = ? WHERE reference = ?",
        (status, now.isoformat(), reference),
    )


def list_orders(db: Database, limit: int = 100) -> list[dict]:
    rows = db.query_all(
        "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    return [dict(r) for r in rows]
