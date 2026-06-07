#!/usr/bin/env python3
"""Send a real test email via the configured Resend/SMTP sender."""

from __future__ import annotations

import sys
import os
import pathlib
import json

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from storefront.auth import ResendCodeSender, SmtpCodeSender, FakeCodeSender


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


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


def _build_sender():
    sf = _load_storefront_settings()
    smtp = sf.get("smtp") or {}

    resend_key = _env("RESEND_API_KEY")
    resend_from = (
        _env("RESEND_FROM")
        or smtp.get("from_addr", "")
        or _env("STOREFRONT_SMTP_FROM_ADDR")
    ).strip()

    if resend_key and resend_from:
        return ResendCodeSender(api_key=resend_key, from_addr=resend_from)

    host = (smtp.get("host") or _env("STOREFRONT_SMTP_HOST")).strip()
    if host:
        username = (smtp.get("username") or _env("STOREFRONT_SMTP_USERNAME")).strip()
        password = (
            smtp.get("password")
            or _env("STOREFRONT_SMTP_PASSWORD")
            or _env("SMTP_PASSWORD")
        )
        from_addr = (
            smtp.get("from_addr")
            or _env("STOREFRONT_SMTP_FROM_ADDR")
            or "no-reply@example.com"
        )
        return SmtpCodeSender(
            host=host,
            port=int(smtp.get("port", _env("STOREFRONT_SMTP_PORT") or 587)),
            username=username,
            password=password,
            from_addr=from_addr,
            use_tls=bool(smtp.get("use_tls", True)),
        )

    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: make storefront-send-test EMAIL=you@example.com")
        return 1

    email = sys.argv[1].strip()
    sender = _build_sender()

    if sender is None:
        print("[ERROR] No email provider configured.")
        print("  Set RESEND_API_KEY + STOREFRONT_SMTP_FROM_ADDR  (Resend)")
        print("  or STOREFRONT_SMTP_HOST + credentials            (SMTP)")
        return 1

    provider = "Resend" if isinstance(sender, ResendCodeSender) else "SMTP"
    print(f"[INFO] Sending test code via {provider} to: {email}")

    try:
        sender.send(email, "123456")
        print(f"[OK] Test email delivered to {email}")
        print("     Subject: 'Your StoryForge confirmation code'")
        print("     Code used: 123456  (this is only a test code)")
        return 0
    except Exception as exc:
        print(f"[ERROR] Delivery failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
