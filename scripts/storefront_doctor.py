#!/usr/bin/env python3
"""Lightweight storefront configuration check used by make targets."""

from __future__ import annotations

import json
import os
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_storefront_settings() -> dict:
    settings_file = ROOT / "settings.json"
    if not settings_file.exists():
        return {}
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    sf = data.get("storefront")
    return sf if isinstance(sf, dict) else {}


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _status(ok: bool, label: str, detail: str = "") -> None:
    prefix = "OK" if ok else "WARN"
    if detail:
        print(f"[{prefix}] {label}: {detail}")
    else:
        print(f"[{prefix}] {label}")


def main() -> int:
    sf = _load_storefront_settings()
    admin = sf.get("admin") or {}
    smtp = sf.get("smtp") or {}

    settings_secret = (sf.get("session_secret") or "").strip()
    env_secret = _env("STOREFRONT_SESSION_SECRET") or _env("SESSION_SECRET")
    file_secret = ""
    secret_file = ROOT / ".storefront" / "session_secret.txt"
    if secret_file.exists():
        try:
            file_secret = secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            file_secret = ""

    if settings_secret:
        _status(True, "Session secret source", "settings.json storefront.session_secret")
    elif env_secret:
        _status(True, "Session secret source", "env STOREFRONT_SESSION_SECRET/SESSION_SECRET")
    elif file_secret:
        _status(True, "Session secret source", ".storefront/session_secret.txt")
    else:
        _status(False, "Session secret source", "none yet, app will auto-generate on first run")

    https_on = bool(sf.get("https", False))
    _status(https_on, "HTTPS cookie mode", "enabled" if https_on else "disabled (set true on VPS with TLS)")

    enabled = bool(admin.get("enabled", False))
    emails = [str(x).strip().lower() for x in (admin.get("emails") or []) if str(x).strip()]
    _status(enabled, "Admin gate", "enabled" if enabled else "disabled")
    _status(bool(emails), "Allowed admin emails", ", ".join(emails) if emails else "empty")

    smtp_host = (smtp.get("host") or _env("STOREFRONT_SMTP_HOST")).strip()
    smtp_user = (smtp.get("username") or _env("STOREFRONT_SMTP_USERNAME")).strip()
    smtp_pass = (smtp.get("password") or _env("STOREFRONT_SMTP_PASSWORD") or _env("SMTP_PASSWORD")).strip()
    smtp_from = (smtp.get("from_addr") or _env("STOREFRONT_SMTP_FROM_ADDR") or "").strip()
    resend_key = _env("RESEND_API_KEY")
    resend_from = (_env("RESEND_FROM") or smtp_from).strip()

    if resend_key:
        _status(True, "Resend API key", "set")
        _status(bool(resend_from), "Resend from address", resend_from or "missing")
        if resend_from.endswith("@example.com") or "example.com>" in resend_from:
            _status(False, "Resend from domain", "example.com is not a verified sender domain")
        print("[INFO] Email provider mode: Resend API")
    else:
        print("[INFO] Email provider mode: SMTP")
        _status(bool(smtp_host), "SMTP host", smtp_host or "missing")
        _status(bool(smtp_user), "SMTP username", smtp_user or "missing")
        _status(bool(smtp_pass), "SMTP password", "set" if smtp_pass else "missing")
        _status(bool(smtp_from), "SMTP from address", smtp_from or "missing")

    print("\nWhat make storefront does each launch:")
    print("1. Loads .env.local into environment (if present).")
    print("2. Runs this storefront config check.")
    print("3. Starts dashboard on http://localhost:8000.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())