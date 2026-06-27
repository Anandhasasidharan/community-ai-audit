"""Authentication — password hashing, JWT, API key generation.

ponytail: stdlib PBKDF2-HMAC-SHA256 (no passlib). stdlib hmac JWT (no PyJWT).
Ceilings: no token refresh, no kid header, no RS256. Upgrade to passlib+PyJWT if
any of those are needed.
"""

import hashlib
import hmac
import json
import base64
import os
import time
from typing import Any

SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, h = stored.split(":")
    return hmac.compare_digest(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex(), h
    )


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "==")


def create_jwt(payload: dict[str, Any], ttl: int = 86400) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(
        json.dumps({**payload, "iat": int(time.time()), "exp": int(time.time()) + ttl}).encode()
    )
    sig = hmac.new(SECRET.encode(), f"{header}.{body}".encode(), "sha256").digest()
    return f"{header}.{body}.{_b64(sig)}"


def decode_jwt(token: str) -> dict | None:
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
        expected = hmac.new(SECRET.encode(), f"{header_b64}.{body_b64}".encode(), "sha256").digest()
        actual = _unb64(sig_b64)
        if not hmac.compare_digest(expected, actual):
            return None
        body = json.loads(_unb64(body_b64))
        if body.get("exp", 0) < time.time():
            return None
        return body
    except Exception:
        return None


def generate_api_key() -> str:
    return os.urandom(32).hex()
