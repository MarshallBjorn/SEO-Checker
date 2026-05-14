import secrets


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(expected: str | None, received: str | None) -> bool:
    if not expected or not received:
        return False
    return secrets.compare_digest(expected, received)
