import hashlib


def stable_txn_id(*parts: str) -> str:
    payload = "|".join(p.strip() for p in parts if p is not None)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
