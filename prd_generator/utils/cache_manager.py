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
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Union, TypeVar
from pathlib import Path

# Define generic type variable T for use in the cached decorator
T = TypeVar('T')

# Get logger
logger = logging.getLogger(__name__)

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
        try:
            # Use absolute path for cache directory
            self.cache_dir = os.path.abspath(cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            logger.debug(f"Cache directory set to: {self.cache_dir}")
        except Exception as e:
            logger.error(f"Error creating cache directory {self.cache_dir}: {e}")
            # Fallback to a temporary directory
            import tempfile
            self.cache_dir = tempfile.gettempdir()
            logger.warning(f"Using temporary directory for cache: {self.cache_dir}")
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """
        Generate a unique cache key based on function arguments
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            A hash string representing the cache key
        """
        try:
            # Convert all arguments to a string representation
            args_str = str(args) + str(sorted(kwargs.items()))
            
            # Create MD5 hash of the arguments string
            hash_obj = hashlib.md5(args_str.encode())
            return hash_obj.hexdigest()
        except Exception as e:
            logger.warning(f"Error generating cache key: {e}")
            # Fallback to a timestamp-based key
            return f"fallback_{int(time.time())}"
    
    def _get_cache_path(self, key: str) -> str:
        """Get the file path for a cache key"""
        return os.path.join(self.cache_dir, f"{key}.cache")
    
    def _ensure_cache_directory(self) -> bool:
        """
        Ensure the cache directory exists and is writable.
        
        Returns:
            bool: True if the cache directory is ready for use, False otherwise
        """
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir, exist_ok=True)
            
            # Verify write permissions by creating a test file
            test_file = os.path.join(self.cache_dir, ".test_write")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except (IOError, OSError) as e:
            logger.error(f"Cache directory {self.cache_dir} is not usable: {e}")
            return False
    
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
                        # Remove expired cache file safely
                        try:
                            os.remove(cache_path)
                        except (OSError, IOError) as e:
                            logger.warning(f"Failed to remove expired cache file {cache_path}: {e}")
                except (pickle.PickleError, OSError, IOError, KeyError) as e:
                    logger.warning(f"Error reading cache file {cache_path}: {e}")
                    # Handle corrupted cache by removing it safely
                    try:
                        if os.path.exists(cache_path):
                            os.remove(cache_path)
                    except (OSError, IOError) as delete_error:
                        logger.warning(f"Failed to remove corrupted cache file: {delete_error}")
        
        return None
    
    def set(self, key: str, value: Any) -> bool:
        """
        Store a value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            
        Returns:
            bool: True if successfully cached, False otherwise
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
            
            # Ensure cache directory exists before attempting to write
            if not self._ensure_cache_directory():
                logger.warning(f"Skipping file cache write due to directory issues")
                return False
                
            # Update file cache
            cache_path = self._get_cache_path(key)
            try:
                # Use a temporary file to prevent corruption on write failures
                temp_path = f"{cache_path}.tmp"
                with open(temp_path, 'wb') as f:
                    data = {
                        'value': value,
                        'timestamp': timestamp
                    }
                    pickle.dump(data, f)
                
                # Rename temp file to target file (atomic operation)
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                os.rename(temp_path, cache_path)
                return True
            except (pickle.PickleError, OSError, IOError) as e:
                logger.warning(f"Failed to write cache to {cache_path}: {e}")
                # Clean up temp file if it exists
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except (OSError, IOError):
                    pass
                return False
    
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
            try:
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    found = True
            except (OSError, IOError) as e:
                logger.warning(f"Failed to remove cache file {cache_path}: {e}")
                
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
            try:
                if os.path.exists(self.cache_dir):
                    for filename in os.listdir(self.cache_dir):
                        if filename.endswith('.cache'):
                            try:
                                os.remove(os.path.join(self.cache_dir, filename))
                                count += 1
                            except (OSError, IOError) as e:
                                logger.warning(f"Failed to remove cache file {filename}: {e}")
            except (OSError, IOError) as e:
                logger.warning(f"Error cleaning cache directory: {e}")
                        
        return count

    def repair(self) -> int:
        """
        Repair the cache by removing corrupted entries
        
        Returns:
            Number of corrupted entries removed
        """
        count = 0
        with self.lock:
            try:
                if not os.path.exists(self.cache_dir):
                    return 0
                    
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.cache'):
                        filepath = os.path.join(self.cache_dir, filename)
                        try:
                            with open(filepath, 'rb') as f:
                                # Attempt to load the cache entry to verify integrity
                                pickle.load(f)
                        except:
                            # Remove corrupted cache file
                            try:
                                os.remove(filepath)
                                count += 1
                                logger.info(f"Removed corrupted cache file: {filename}")
                            except (OSError, IOError):
                                pass
            except (OSError, IOError) as e:
                logger.warning(f"Error during cache repair: {e}")
                
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
                try:
                    cache_key = f"{func.__module__}.{func.__name__}:{self._get_cache_key(*args, **kwargs)}"
                    
                    # Try to get from cache
                    try:
                        cached_result = self.get(cache_key)
                        if cached_result is not None:
                            logger.debug(f"Cache hit for {func.__name__}")
                            return cached_result
                    except Exception as e:
                        logger.warning(f"Error retrieving from cache for {func.__name__}: {e}")
                        # Continue with function execution
                    
                    # Call the function since cache miss or error
                    logger.debug(f"Cache miss for {func.__name__}, executing function")
                    result = func(*args, **kwargs)
                    
                    # Store in cache, ignoring any errors
                    try:
                        self.set(cache_key, result)
                    except Exception as e:
                        logger.warning(f"Failed to cache result for {func.__name__}: {e}")
                    
                    return result
                except Exception as e:
                    # If anything goes wrong with caching, execute the function directly
                    logger.warning(f"Cache mechanism failed for {func.__name__}: {e}")
                    return func(*args, **kwargs)
            
            # Add invalidation method to the wrapped function
            def invalidate_cache(*args, **kwargs):
                try:
                    cache_key = f"{func.__module__}.{func.__name__}:{self._get_cache_key(*args, **kwargs)}"
                    return self.invalidate(cache_key)
                except Exception as e:
                    logger.warning(f"Failed to invalidate cache for {func.__name__}: {e}")
                    return False
            
            wrapper.invalidate_cache = invalidate_cache
            return wrapper
        
        return decorator

# Default cache directory location in the application data directory
def get_default_cache_dir():
    """Get the default cache directory path"""
    try:
        # Use the user's application data directory
        app_data = os.getenv('APPDATA') or os.path.expanduser('~/.local/share')
        cache_dir = os.path.join(app_data, 'prd_generator', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    except Exception:
        # Fallback to a directory in the current path
        base_dir = os.path.abspath(os.path.curdir)
        cache_dir = os.path.join(base_dir, '.cache')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

# Global cache instance with better default location
cache = CacheManager(cache_dir=get_default_cache_dir())

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