from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    """Genera un hash Argon2id. Uso: generar `MINDOS_ADMIN_PASSWORD_HASH` para el .env."""
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Hash vacío/corrupto/formato inválido: falla cerrado, nunca lanza hacia el caller de auth.
        return False


def create_access_token(subject: str, secret: str, algorithm: str, expiry_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=expiry_minutes)}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, secret: str, algorithm: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.InvalidTokenError:
        return None
