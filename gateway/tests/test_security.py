"""F3-T1: hashing Argon2 de contraseñas y emisión/verificación de JWT para el login mono-usuario."""
import time

from gateway.src.application.services.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_a_verifiable_argon2_hash():
    hashed = hash_password("correcto-caballo-batería-grapadora")
    assert hashed.startswith("$argon2")
    assert verify_password("correcto-caballo-batería-grapadora", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("la-correcta")
    assert verify_password("la-incorrecta", hashed) is False


def test_verify_password_fails_closed_on_empty_or_corrupt_hash():
    assert verify_password("cualquiera", "") is False
    assert verify_password("cualquiera", "no-es-un-hash-argon2-valido") is False


def test_access_token_roundtrip():
    token = create_access_token("damian", secret="s3cr3t", algorithm="HS256", expiry_minutes=60)
    payload = decode_access_token(token, secret="s3cr3t", algorithm="HS256")
    assert payload is not None
    assert payload["sub"] == "damian"


def test_access_token_rejected_with_wrong_secret():
    token = create_access_token("damian", secret="s3cr3t", algorithm="HS256", expiry_minutes=60)
    assert decode_access_token(token, secret="otro-secreto", algorithm="HS256") is None


def test_access_token_rejected_when_expired():
    token = create_access_token("damian", secret="s3cr3t", algorithm="HS256", expiry_minutes=0)
    time.sleep(1.1)
    assert decode_access_token(token, secret="s3cr3t", algorithm="HS256") is None
