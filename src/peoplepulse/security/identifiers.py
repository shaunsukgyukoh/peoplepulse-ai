import hashlib
import hmac


def pseudonymize(value: str, secret: str, *, namespace: str) -> str:
    """Create a stable, non-reversible HMAC identifier for internal aggregation."""
    message = f"{namespace}:{value}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return digest[:32]
