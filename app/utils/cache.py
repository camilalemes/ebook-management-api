"""Caching utilities for the Calibre Sync API."""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, Union
import hashlib
import json

from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)

# Type variables for generic functions
F = TypeVar('F', bound=Callable[..., Any])
T = TypeVar('T')


class InMemoryCache:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: int = None):
        self.default_ttl = default_ttl or settings.CACHE_TTL
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate a cache key from function arguments."""
        # Create a deterministic key from args and kwargs
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items()) if kwargs else {}
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        current_time = time.time()
        
        # Check if expired
        if current_time - entry['timestamp'] > entry['ttl']:
            self.delete(key)
            return None
        
        # Update access time
        self._access_times[key] = current_time
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache with optional TTL."""
        cache_ttl = ttl or self.default_ttl
        current_time = time.time()
        
        self._cache[key] = {
            'value': value,
            'timestamp': current_time,
            'ttl': cache_ttl
        }
        self._access_times[key] = current_time
        
        # Clean up expired entries periodically
        if len(self._cache) % 100 == 0:  # Clean every 100 entries
            self._cleanup_expired()
    
    def delete(self, key: str) -> bool:
        """Delete a specific key from cache."""
        if key in self._cache:
            del self._cache[key]
            self._access_times.pop(key, None)
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_times.clear()
        logger.info("Cache cleared")
    
    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if current_time - entry['timestamp'] > entry['ttl']:
                expired_keys.append(key)
        
        for key in expired_keys:
            self.delete(key)
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'total_entries': len(self._cache),
            'cache_hits': getattr(self, '_hits', 0),
            'cache_misses': getattr(self, '_misses', 0),
            'hit_ratio': getattr(self, '_hits', 0) / max(getattr(self, '_hits', 0) + getattr(self, '_misses', 0), 1)
        }


# Global cache instance
_cache = InMemoryCache()


def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (uses default if None)
        key_prefix: Prefix for cache keys
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{_cache._generate_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                _cache._hits = getattr(_cache, '_hits', 0) + 1
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Cache miss - execute function
            _cache._misses = getattr(_cache, '_misses', 0) + 1
            logger.debug(f"Cache miss for {func.__name__}")
            
            result = func(*args, **kwargs)
            
            # Store in cache
            _cache.set(cache_key, result, ttl)
            
            return result
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{_cache._generate_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                _cache._hits = getattr(_cache, '_hits', 0) + 1
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Cache miss - execute function
            _cache._misses = getattr(_cache, '_misses', 0) + 1
            logger.debug(f"Cache miss for {func.__name__}")
            
            result = await func(*args, **kwargs)
            
            # Store in cache
            _cache.set(cache_key, result, ttl)
            
            return result
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def cache_invalidate(pattern: str = None) -> None:
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern: Pattern to match cache keys (None clears all)
    """
    if pattern is None:
        _cache.clear()
    else:
        keys_to_delete = [key for key in _cache._cache.keys() if pattern in key]
        for key in keys_to_delete:
            _cache.delete(key)
        logger.info(f"Invalidated {len(keys_to_delete)} cache entries matching pattern: {pattern}")


def get_cache_stats() -> Dict[str, Any]:
    """Get current cache statistics."""
    return _cache.stats()


# Decorator for common cache patterns
def cache_books(ttl: int = 300):  # 5 minutes default
    """Cache decorator specifically for book-related functions."""
    return cached(ttl=ttl, key_prefix="books")


def cache_metadata(ttl: int = 600):  # 10 minutes default
    """Cache decorator specifically for metadata functions."""
    return cached(ttl=ttl, key_prefix="metadata")


def cache_covers(ttl: int = 3600):  # 1 hour default
    """Cache decorator specifically for cover images."""
    return cached(ttl=ttl, key_prefix="covers")