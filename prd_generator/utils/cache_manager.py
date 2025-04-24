"""
Cache manager for the PRD Generator.

This module provides a robust caching system to store and retrieve results of computationally 
expensive or API-dependent operations, reducing redundant calls and improving performance.
"""

import hashlib
import json
import os
import pickle
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union, TypeVar

# Define generic type variable T for use in the cached decorator
T = TypeVar('T')

class CacheManager:
    """Manages caching for expensive operations like LLM API calls"""
    
    def __init__(self, 
                 cache_dir: str = ".cache", 
                 ttl: int = 86400,  # 24 hours default TTL
                 max_size: int = 1000):
        """
        Initialize the cache manager
        
        Args:
            cache_dir: Directory to store cache files
            ttl: Time-to-live for cache entries in seconds
            max_size: Maximum number of items to keep in memory cache
        """
        self.cache_dir = cache_dir
        self.ttl = ttl
        self.max_size = max_size
        self.memory_cache: Dict[str, Tuple[Any, float]] = {}
        self.lock = threading.RLock()
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """
        Generate a unique cache key based on function arguments
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            A hash string representing the cache key
        """
        # Convert all arguments to a string representation
        args_str = str(args) + str(sorted(kwargs.items()))
        
        # Create MD5 hash of the arguments string
        hash_obj = hashlib.md5(args_str.encode())
        return hash_obj.hexdigest()
    
    def _get_cache_path(self, key: str) -> str:
        """Get the file path for a cache key"""
        return os.path.join(self.cache_dir, f"{key}.cache")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Cached value or None if not found or expired
        """
        with self.lock:
            # Try memory cache first
            if key in self.memory_cache:
                value, timestamp = self.memory_cache[key]
                if time.time() - timestamp <= self.ttl:
                    return value
                else:
                    # Remove expired entry
                    del self.memory_cache[key]
            
            # Try file cache
            cache_path = self._get_cache_path(key)
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'rb') as f:
                        data = pickle.load(f)
                        
                    timestamp = data['timestamp']
                    # Check if cache is still valid
                    if time.time() - timestamp <= self.ttl:
                        # Update memory cache
                        self.memory_cache[key] = (data['value'], timestamp)
                        return data['value']
                    else:
                        # Remove expired cache file
                        os.remove(cache_path)
                except (pickle.PickleError, OSError, KeyError):
                    # Handle corrupted cache or other issues
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
        
        return None
    
    def set(self, key: str, value: Any) -> None:
        """
        Store a value in cache
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            timestamp = time.time()
            
            # Update memory cache
            self.memory_cache[key] = (value, timestamp)
            
            # Limit memory cache size
            if len(self.memory_cache) > self.max_size:
                # Remove oldest items
                sorted_items = sorted(
                    self.memory_cache.items(),
                    key=lambda x: x[1][1]  # Sort by timestamp
                )
                # Remove oldest 10% of items
                items_to_remove = sorted_items[:max(1, len(sorted_items) // 10)]
                for old_key, _ in items_to_remove:
                    del self.memory_cache[old_key]
            
            # Update file cache
            cache_path = self._get_cache_path(key)
            try:
                with open(cache_path, 'wb') as f:
                    data = {
                        'value': value,
                        'timestamp': timestamp
                    }
                    pickle.dump(data, f)
            except (pickle.PickleError, OSError) as e:
                print(f"Warning: Failed to write cache to {cache_path}: {e}")
    
    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            True if the key was found and invalidated, False otherwise
        """
        with self.lock:
            found = False
            
            # Remove from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
                found = True
            
            # Remove from file cache
            cache_path = self._get_cache_path(key)
            if os.path.exists(cache_path):
                os.remove(cache_path)
                found = True
                
        return found
    
    def clear(self) -> int:
        """
        Clear all cache entries
        
        Returns:
            Number of entries cleared
        """
        with self.lock:
            # Count memory cache entries
            count = len(self.memory_cache)
            self.memory_cache.clear()
            
            # Clear file cache
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    try:
                        os.remove(os.path.join(self.cache_dir, filename))
                        count += 1
                    except OSError:
                        pass
                        
        return count
    
    def cached(self, ttl: Optional[int] = None) -> Callable:
        """
        Decorator for caching function results
        
        Args:
            ttl: Optional TTL override for this function's cache
            
        Returns:
            Decorated function with caching capability
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate a cache key from function name and arguments
                cache_key = f"{func.__module__}.{func.__name__}:{self._get_cache_key(*args, **kwargs)}"
                
                # Try to get from cache
                cached_result = self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Call the function
                result = func(*args, **kwargs)
                
                # Store in cache
                self.set(cache_key, result)
                
                return result
            
            # Add invalidation method to the wrapped function
            def invalidate_cache(*args, **kwargs):
                cache_key = f"{func.__module__}.{func.__name__}:{self._get_cache_key(*args, **kwargs)}"
                return self.invalidate(cache_key)
            
            wrapper.invalidate_cache = invalidate_cache
            return wrapper
        
        return decorator

# Global cache instance for convenience
cache = CacheManager()

# Decorator for caching with default TTL
def cached(ttl: Optional[int] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for caching function results.
    
    Args:
        ttl: Optional time-to-live for cache entries in seconds
        
    Returns:
        Callable: Decorated function
    """
    return cache.cached(ttl)