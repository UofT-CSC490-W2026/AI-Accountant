from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from functools import lru_cache
from urllib.error import URLError
from urllib.request import urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from auth.schemas import TokenPayload
from config import get_settings


@lru_cache(maxsize=4)
def _load_jwks_document(jwks_url: str, jwks_json: str | None) -> dict[str, object]:
    if jwks_json:
        return json.loads(jwks_json)

    try:  # pragma: no cover
        with urlopen(jwks_url, timeout=5) as response:
            return json.load(response)
    except URLError as exc:
        raise ValueError("Unable to load Cognito JWKS.") from exc


@lru_cache(maxsize=32)
def _get_signing_key(kid: str, jwks_url: str, jwks_json: str | None) -> rsa.RSAPublicKey:
    jwks = _load_jwks_document(jwks_url, jwks_json)
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid:
            return _public_key_from_jwk(key_data)
    raise ValueError("Unknown token key id.")


def clear_caches() -> None:
    _load_jwks_document.cache_clear()
    _get_signing_key.cache_clear()


def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()

    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        header = _decode_json_segment(header_segment)
        claims = _decode_json_segment(payload_segment)
    except ValueError as exc:
        raise ValueError("Malformed access token.") from exc

    kid = header.get("kid")
    if not kid:
        raise ValueError("Missing token key id.")

    token_use = claims.get("token_use")
    if token_use not in {"access", "id"}:
        raise ValueError("Unsupported token use.")

    key = _get_signing_key(kid, settings.cognito_jwks_url, settings.COGNITO_JWKS_JSON)
    try:
        key.verify(
            _b64url_decode(signature_segment),
            f"{header_segment}.{payload_segment}".encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as exc:
        raise ValueError("Invalid token signature.") from exc
    except ValueError as exc:
        raise ValueError("Malformed access token.") from exc

    if claims.get("iss") != settings.cognito_issuer:
        raise ValueError("Unexpected token issuer.")

    exp = claims.get("exp")
    if not isinstance(exp, int):
        raise ValueError("Invalid Cognito token.")
    now = int(datetime.now(timezone.utc).timestamp())
    if exp <= now:
        raise ValueError("Token has expired.")

    if token_use == "access" and settings.COGNITO_CLIENT_ID:
        if claims.get("client_id") != settings.COGNITO_CLIENT_ID:
            raise ValueError("Unexpected Cognito app client.")
    if token_use == "id" and settings.COGNITO_CLIENT_ID:
        if claims.get("aud") != settings.COGNITO_CLIENT_ID:
            raise ValueError("Unexpected Cognito app client.")

    return TokenPayload.model_validate(claims)


def _decode_json_segment(segment: str) -> dict[str, object]:
    decoded = _b64url_decode(segment)
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError("JWT segment is not an object.")
    return data


def _b64url_decode(value: str) -> bytes:
    padding_value = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding_value).encode("ascii"))


def _public_key_from_jwk(jwk: dict[str, object]) -> rsa.RSAPublicKey:
    modulus = int.from_bytes(_b64url_decode(str(jwk["n"])), "big")
    exponent = int.from_bytes(_b64url_decode(str(jwk["e"])), "big")
    return rsa.RSAPublicNumbers(exponent, modulus).public_key()
