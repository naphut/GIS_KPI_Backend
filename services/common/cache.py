import logging
import redis.asyncio as redis

logger = logging.getLogger("cache_service")
logging.basicConfig(level=logging.INFO)

class InMemoryCache:
    """
    Thread-safe, synchronous-looking async mock cache.
    Acts as a silent fallback if Redis is not running or fails.
    """
    def __init__(self):
        self._store = {}
        logger.info("Initializing fallback In-Memory Cache.")

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        self._store[key] = value

    async def delete(self, key: str):
        if key in self._store:
            del self._store[key]

class RedisCache:
    """
    Redis client proxy with automatic fallbacks for maximum production resilience.
    """
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client = None

    async def connect(self):
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            await self.client.ping()
            logger.info(f"Successfully connected to Redis Cache at {self.redis_url}")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis at {self.redis_url}: {e}. "
                f"Falling back to InMemoryCache to prevent system downtime."
            )
            self.client = InMemoryCache()

    async def get(self, key: str):
        if not self.client:
            await self.connect()
        try:
            return await self.client.get(key)
        except Exception as e:
            logger.error(f"Redis get failed: {e}. Falling back to In-Memory.")
            self.client = InMemoryCache()
            return await self.client.get(key)

    async def set(self, key: str, value: str, ex: int = None):
        if not self.client:
            await self.connect()
        try:
            await self.client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"Redis set failed: {e}. Falling back to In-Memory.")
            self.client = InMemoryCache()
            await self.client.set(key, value, ex=ex)

    async def delete(self, key: str):
        if not self.client:
            await self.connect()
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete failed: {e}. Falling back to In-Memory.")
            self.client = InMemoryCache()
            await self.client.delete(key)

# Global Cache Instance
cache = RedisCache("redis://localhost:6379")
