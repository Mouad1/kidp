import datetime as dt
import hashlib
import hmac
import json
import pathlib
import secrets
import smtplib
from dataclasses import dataclass, asdict
from email.message import EmailMessage
from typing import Protocol

MAX_ATTEMPTS = 5


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash(email: str, code: str, salt: str) -> str:
    return hmac.new(salt.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


class CodeSender(Protocol):
    def send(self, email: str, code: str) -> None: ...


class FakeCodeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, email: str, code: str) -> None:
        self.sent.append((email, code))


class SmtpCodeSender:
    def __init__(self, host: str, port: int, username: str, password: str,
                 from_addr: str, use_tls: bool = True):
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.from_addr, self.use_tls = from_addr, use_tls

    def send(self, email: str, code: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = "Your StoryForge confirmation code"
        msg["From"] = self.from_addr
        msg["To"] = email
        msg.set_content(f"Your confirmation code is {code}. It expires in 10 minutes.")
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(msg)


@dataclass
class CodeRecord:
    email: str
    code_hash: str
    salt: str
    expires_at: str  # ISO 8601
    attempts: int = 0


class AuthStore:
    """File-backed JSON store: email -> CodeRecord. Sufficient for low volume."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))

    def put(self, rec: CodeRecord) -> None:
        data = self._load()
        data[rec.email] = asdict(rec)
        self._save(data)

    def get(self, email: str) -> CodeRecord | None:
        raw = self._load().get(email)
        return CodeRecord(**raw) if raw else None

    def delete(self, email: str) -> None:
        data = self._load()
        data.pop(email, None)
        self._save(data)


def request_code(email: str, now: dt.datetime, code_sender: CodeSender,
                 store: AuthStore, ttl_seconds: int = 600) -> None:
    code = generate_code()
    salt = secrets.token_hex(16)
    rec = CodeRecord(
        email=email,
        code_hash=_hash(email, code, salt),
        salt=salt,
        expires_at=(now + dt.timedelta(seconds=ttl_seconds)).isoformat(),
    )
    store.put(rec)
    code_sender.send(email, code)


def verify_code(email: str, code: str, now: dt.datetime, store: AuthStore) -> bool:
    rec = store.get(email)
    if rec is None:
        return False
    if rec.attempts >= MAX_ATTEMPTS:
        return False
    if now > dt.datetime.fromisoformat(rec.expires_at):
        return False
    candidate = _hash(email, code, rec.salt)
    if hmac.compare_digest(candidate, rec.code_hash):
        store.delete(email)
        return True
    rec.attempts += 1
    store.put(rec)
    return False
