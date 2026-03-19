from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 8


def validate_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if password.lower() == password or password.upper() == password:
        raise ValueError("Password must include both uppercase and lowercase characters.")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must include at least one digit.")


def hash_password(password: str) -> str:
    validate_password_policy(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, raw_iterations, encoded_salt, encoded_digest = password_hash.split("$", maxsplit=3)
    except ValueError:
        return False
    if algorithm != f"pbkdf2_{PBKDF2_ALGORITHM}":
        return False
    iterations = int(raw_iterations)
    salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
    expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
    actual = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
