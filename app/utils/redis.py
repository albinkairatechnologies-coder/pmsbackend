import redis
import json
import os
import logging

logger = logging.getLogger('kairaflow.cache')

class RedisCache:
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.password = os.getenv('REDIS_PASSWORD', None)
        self.enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'
        self.client = None
        self._fallback_active = False

        if self.enabled:
            try:
                self.client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    decode_responses=True,
                    socket_connect_timeout=2
                )
                # Test connection
                self.client.ping()
                logger.info(f"Connected to Redis at {self.host}:{self.port}")
            except Exception as e:
                logger.warning(f"Redis is disabled or connection failed ({e}). Falling back to database-only mode.")
                self._fallback_active = True
                self.client = None
        else:
            logger.info("Redis cache is explicitly disabled via configuration.")

    def get(self, key):
        if not self.enabled or self._fallback_active or not self.client:
            return None
        try:
            val = self.client.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
        return None

    def set(self, key, value, timeout=60):
        if not self.enabled or self._fallback_active or not self.client:
            return False
        try:
            serialized = json.dumps(value)
            self.client.setex(key, timeout, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
        return False

    def delete(self, key):
        if not self.enabled or self._fallback_active or not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error for key '{key}': {e}")
        return False

    def delete_pattern(self, pattern):
        if not self.enabled or self._fallback_active or not self.client:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN error for pattern '{pattern}': {e}")
        return False

# Global Cache instance
cache = RedisCache()
