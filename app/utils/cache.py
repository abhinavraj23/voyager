import hashlib
import json
import logging
import time
from typing import Any, Optional, Callable
from functools import wraps
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """Cache manager supporting both in-memory and Redis caching"""
    
    def __init__(self):
        self.cache_type = settings.cache_type
        self._memory_cache = {}
        self._redis_client = None
        
        if self.cache_type == "redis" and settings.redis_url:
            try:
                self._redis_client = redis.from_url(settings.redis_url)
                logger.info("Redis cache initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}. Falling back to memory cache.")
                self.cache_type = "memory"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if self.cache_type == "redis" and self._redis_client:
                value = await self._redis_client.get(key)
                return json.loads(value) if value else None
            else:
                if key in self._memory_cache:
                    value, expiry = self._memory_cache[key]
                    if expiry > time.time():
                        return value
                    else:
                        del self._memory_cache[key]
                return None
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL"""
        try:
            if ttl is None:
                ttl = settings.cache_ttl
                
            if self.cache_type == "redis" and self._redis_client:
                await self._redis_client.setex(key, ttl, json.dumps(value))
            else:
                self._memory_cache[key] = (value, time.time() + ttl)
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            if self.cache_type == "redis" and self._redis_client:
                await self._redis_client.delete(key)
            else:
                self._memory_cache.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            return False
    
    def generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from function arguments"""
        # Filter out non-serializable objects (like service instances)
        serializable_args = []
        for arg in args:
            if self._is_serializable(arg):
                serializable_args.append(arg)
            else:
                # For non-serializable objects, use their class name and id
                serializable_args.append(f"{arg.__class__.__name__}_{id(arg)}")
        
        serializable_kwargs = {}
        for key, value in kwargs.items():
            if self._is_serializable(value):
                serializable_kwargs[key] = value
            else:
                # For non-serializable objects, use their class name and id
                serializable_kwargs[key] = f"{value.__class__.__name__}_{id(value)}"
        
        key_data = {
            'args': serializable_args,
            'kwargs': sorted(serializable_kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _is_serializable(self, obj) -> bool:
        """Check if an object is JSON serializable"""
        try:
            json.dumps(obj)
            return True
        except (TypeError, ValueError):
            return False

# Global cache manager instance
cache_manager = CacheManager()

def cached(ttl: int = None, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{cache_manager.generate_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for key: {cache_key}, cached result")
            
            return result
        return wrapper
    return decorator 