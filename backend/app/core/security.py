"""Passphrase lock: scrypt hashing, in-memory session tokens, brute-force back-off.

The passphrase is never stored; only a salted scrypt hash lives in the local
settings table.  Sessions are random tokens kept in memory, so restarting the
backend re-locks the app.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
MIN_PASSPHRASE_LEN = 8


def hash_passphrase(passphrase: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        passphrase.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N, SCRYPT_R, SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode(),
    )


def verify_passphrase(passphrase: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            passphrase.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class SessionStore:
    """Thread-safe store of unlock tokens with expiry and failed-attempt throttling."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._tokens: dict[str, float] = {}
        self._failures = 0
        self._locked_until = 0.0
        self._lock = threading.Lock()

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = time.time() + self._ttl
            self._failures = 0
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            expiry = self._tokens.get(token)
            if expiry is None:
                return False
            if expiry < time.time():
                self._tokens.pop(token, None)
                return False
            return True

    def revoke(self, token: str | None) -> None:
        with self._lock:
            if token:
                self._tokens.pop(token, None)

    def revoke_all(self) -> None:
        with self._lock:
            self._tokens.clear()

    def retry_after(self) -> int:
        with self._lock:
            return max(0, int(self._locked_until - time.time()))

    def record_failure(self) -> None:
        """Exponential back-off after 3 wrong attempts (capped at 5 minutes)."""
        with self._lock:
            self._failures += 1
            if self._failures >= 3:
                delay = min(300, 2 ** (self._failures - 2))
                self._locked_until = time.time() + delay
