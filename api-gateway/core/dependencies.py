import redis.asyncio as redis
from typing import Optional

from config.settings import get_settings

# Redis client singleton
_redis_client: Optional[redis.Redis] = None

async def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            db=settings.redis_db,
            max_connections=settings.redis_max_connections,
            decode_responses=True
        )
    return _redis_client