import asyncio
import time
from typing import Optional, Any, Callable
from functools import wraps
from app.config import settings
from app.logger import setup_logger

logger = setup_logger(__name__)

class AsyncLRUCache:
    def __init__(self, ttl: int = 300):
        self.cache = {}
        self.ttl = ttl
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp <= self.ttl:
                    return value
                else:
                    del self.cache[key]
        return None
    
    async def set(self, key: str, value: Any):
        """Set value in cache with current timestamp"""
        async with self.lock:
            self.cache[key] = (value, time.time())
    
    async def delete(self, key: str):
        """Delete key from cache"""
        async with self.lock:
            self.cache.pop(key, None)
    
    async def clear(self):
        """Clear all cache"""
        async with self.lock:
            self.cache.clear()

def async_cached(ttl: Optional[int] = None):
    """Decorator for async function caching"""
    def decorator(func):
        cache = AsyncLRUCache(ttl or settings.CACHE_TTL)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{args}:{kwargs}"
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {key}")
                return cached_value
            
            # If not in cache, call function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result)
            logger.debug(f"Cache miss for {key}, value cached")
            return result
        
        # Add cache control methods to wrapper
        wrapper.cache = cache
        wrapper.clear_cache = cache.clear
        wrapper.delete_from_cache = cache.delete
        
        return wrapper
    return decorator

# Create global caches for common data
folder_cache = AsyncLRUCache(settings.FOLDER_CACHE_TTL)
user_cache = AsyncLRUCache(settings.CACHE_TTL) 