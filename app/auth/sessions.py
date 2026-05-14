import json
import secrets
from datetime import UTC, datetime

import redis.asyncio as aioredis

from app.config import settings

_redis = aioredis.from_url(settings.session_redis_url, decode_responses=True)

_PREFIX = "session:"


async def create_session(user_id: str) -> tuple[str, str]:
    """Tworzy nową sesję w Redis. Zwraca (session_id, token)."""
    session_id = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    payload = {
        "user_id": user_id,
        "csrf_token": csrf_token,
        "created_at": datetime.now(UTC).isoformat(),
    }
    await _redis.set(_PREFIX + session_id, json.dumps(payload), ex=settings.session_ttl_seconds)
    return session_id, csrf_token


async def get_session(session_id: str) -> dict | None:
    raw = await _redis.get(_PREFIX + session_id)
    return json.loads(raw) if raw else None


async def delete_session(session_id: str) -> None:
    await _redis.delete(_PREFIX + session_id)
