import pathlib

import dashboard.app as appmod


def test_store_session_secret_uses_settings_value(monkeypatch):
    monkeypatch.setattr(appmod, "_SF_SECRET_CACHE", None)
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {"session_secret": "from-settings"})

    secret = appmod._store_session_secret()

    assert secret == "from-settings"


def test_store_session_secret_uses_env_when_settings_empty(monkeypatch):
    monkeypatch.setattr(appmod, "_SF_SECRET_CACHE", None)
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.setattr(appmod, "ROOT", pathlib.Path("/tmp/does-not-matter"))
    monkeypatch.setenv("STOREFRONT_SESSION_SECRET", "from-env")

    secret = appmod._store_session_secret()

    assert secret == "from-env"


def test_store_session_secret_generates_and_persists(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "_SF_SECRET_CACHE", None)
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.delenv("STOREFRONT_SESSION_SECRET", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setattr(appmod, "ROOT", tmp_path)

    first = appmod._store_session_secret()
    monkeypatch.setattr(appmod, "_SF_SECRET_CACHE", None)
    second = appmod._store_session_secret()

    assert first
    assert first == second
    saved = (tmp_path / ".storefront" / "session_secret.txt").read_text(encoding="utf-8").strip()
    assert saved == first


def test_store_code_sender_reads_smtp_from_env(monkeypatch):
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.setenv("STOREFRONT_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("STOREFRONT_SMTP_PORT", "2525")
    monkeypatch.setenv("STOREFRONT_SMTP_USERNAME", "u1")
    monkeypatch.setenv("STOREFRONT_SMTP_PASSWORD", "p1")
    monkeypatch.setenv("STOREFRONT_SMTP_FROM_ADDR", "noreply@example.com")

    sender = appmod._store_code_sender()

    assert isinstance(sender, appmod._SfSmtpCodeSender)
    assert sender.host == "smtp.example.com"
    assert sender.port == 2525
    assert sender.username == "u1"
    assert sender.password == "p1"
    assert sender.from_addr == "noreply@example.com"


def test_store_code_sender_prefers_settings_over_env(monkeypatch):
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {
        "smtp": {
            "host": "smtp.settings.local",
            "port": 587,
            "username": "settings-user",
            "password": "settings-pass",
            "from_addr": "from@settings.local",
            "use_tls": True,
        }
    })
    monkeypatch.setenv("STOREFRONT_SMTP_HOST", "smtp.env.local")
    monkeypatch.setenv("STOREFRONT_SMTP_USERNAME", "env-user")
    monkeypatch.setenv("STOREFRONT_SMTP_PASSWORD", "env-pass")

    sender = appmod._store_code_sender()

    assert isinstance(sender, appmod._SfSmtpCodeSender)
    assert sender.host == "smtp.settings.local"
    assert sender.username == "settings-user"
    assert sender.password == "settings-pass"


def test_store_code_sender_uses_resend_when_api_key_present(monkeypatch):
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.delenv("STOREFRONT_SMTP_HOST", raising=False)
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("STOREFRONT_SMTP_FROM_ADDR", "Auth <no-reply@example.com>")

    sender = appmod._store_code_sender()

    assert isinstance(sender, appmod._SfResendCodeSender)
    assert sender.api_key == "re_test_key"
    assert sender.from_addr == "Auth <no-reply@example.com>"


def test_store_code_sender_prefers_resend_over_smtp(monkeypatch):
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("STOREFRONT_SMTP_FROM_ADDR", "Auth <no-reply@example.com>")
    monkeypatch.setenv("STOREFRONT_SMTP_HOST", "smtp.example.com")

    sender = appmod._store_code_sender()

    assert isinstance(sender, appmod._SfResendCodeSender)