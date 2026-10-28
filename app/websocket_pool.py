"""
WebSocket Connection Pooling Service

Manages a pool of WebSocket connections to reduce connection overhead
and improve performance for concurrent users.

Features:
- Connection reuse across requests
- Health monitoring with automatic reconnection
- Connection lifecycle management
- Thread-safe operations
"""

import asyncio
import logging
import threading
import time
from typing import Dict, Optional
from collections import defaultdict
from app.websocket_service import WebSocketService

logger = logging.getLogger(__name__)


class WebSocketPool:
    """
    Connection pool manager for WebSocket connections.
    
    Benefits:
    - Reduces connection overhead (no reconnect for each request)
    - Monitors connection health
    - Automatic reconnection on failure
    - Thread-safe connection sharing
    """
    
    def __init__(self, max_connections: int = 100, idle_timeout: int = 300):
        """
        Initialize WebSocket connection pool.
        
        Args:
            max_connections: Maximum number of pooled connections (default: 100)
            idle_timeout: Seconds before idle connection is closed (default: 300)
        """
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout
        
        # Connection storage: {user_id: {'service': WebSocketService, 'last_used': timestamp, 'in_use': bool}}
        self._connections: Dict[str, dict] = {}
        
        # Lock for thread-safe operations
        self._lock = threading.RLock()
        
        # Connection usage statistics
        self._stats = {
            'total_connections': 0,
            'active_connections': 0,
            'connection_hits': 0,  # Reused existing connection
            'connection_misses': 0,  # Created new connection
            'reconnections': 0,
            'health_checks': 0,
            'evictions': 0
        }
        
        # Start background health check thread
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name='WebSocketPoolHealthCheck'
        )
        self._health_check_thread.start()
        
        logger.info(f"WebSocketPool initialized (max_connections={max_connections}, idle_timeout={idle_timeout}s)")
    
    def get_connection(self, user_id: str, access_token: str) -> WebSocketService:
        """
        Get a WebSocket connection for the user (from pool or create new).
        
        Args:
            user_id: User/account ID
            access_token: Deriv API access token
            
        Returns:
            WebSocketService instance (ready to use)
        """
        with self._lock:
            # Check if connection exists in pool
            if user_id in self._connections:
                conn_data = self._connections[user_id]
                service = conn_data['service']
                
                # Verify connection is healthy
                if self._is_connection_healthy(service):
                    # Update last used timestamp
                    conn_data['last_used'] = time.time()
                    conn_data['in_use'] = True
                    
                    self._stats['connection_hits'] += 1
                    logger.debug(f"Reusing WebSocket connection for user {user_id}")
                    return service
                else:
                    # Connection unhealthy, remove from pool
                    logger.warning(f"Removing unhealthy connection for user {user_id}")
                    self._remove_connection(user_id)
            
            # Connection not found or unhealthy, create new one
            return self._create_connection(user_id, access_token)
    
    def release_connection(self, user_id: str):
        """
        Release a connection back to the pool (mark as not in use).
        
        Args:
            user_id: User/account ID
        """
        with self._lock:
            if user_id in self._connections:
                self._connections[user_id]['in_use'] = False
                self._connections[user_id]['last_used'] = time.time()
                logger.debug(f"Released WebSocket connection for user {user_id}")
    
    def close_connection(self, user_id: str):
        """
        Close and remove a connection from the pool.
        
        Args:
            user_id: User/account ID
        """
        with self._lock:
            self._remove_connection(user_id)
            logger.info(f"Closed WebSocket connection for user {user_id}")
    
    def close_all(self):
        """
        Close all connections in the pool (for shutdown).
        """
        with self._lock:
            user_ids = list(self._connections.keys())
            for user_id in user_ids:
                self._remove_connection(user_id)
            logger.info(f"Closed all WebSocket connections ({len(user_ids)} total)")
    
    def get_stats(self) -> dict:
        """
        Get connection pool statistics.
        
        Returns:
            Dictionary with pool metrics
        """
        with self._lock:
            return {
                **self._stats,
                'pool_size': len(self._connections),
                'active_connections': sum(1 for c in self._connections.values() if c['in_use']),
                'idle_connections': sum(1 for c in self._connections.values() if not c['in_use']),
                'hit_rate': (
                    self._stats['connection_hits'] / 
                    (self._stats['connection_hits'] + self._stats['connection_misses'])
                    if (self._stats['connection_hits'] + self._stats['connection_misses']) > 0 
                    else 0
                )
            }
    
    # ==================== PRIVATE METHODS ====================
    
    def _create_connection(self, user_id: str, access_token: str) -> WebSocketService:
        """
        Create a new WebSocket connection and add to pool.
        
        Args:
            user_id: User/account ID
            access_token: Deriv API access token
            
        Returns:
            New WebSocketService instance
        """
        # Check if pool is full
        if len(self._connections) >= self.max_connections:
            self._evict_idle_connection()
        
        # Create new connection
        service = WebSocketService(access_token)
        
        # Add to pool
        self._connections[user_id] = {
            'service': service,
            'last_used': time.time(),
            'in_use': True,
            'created_at': time.time()
        }
        
        self._stats['total_connections'] += 1
        self._stats['connection_misses'] += 1
        
        logger.info(f"Created new WebSocket connection for user {user_id} (pool size: {len(self._connections)})")
        return service
    
    def _remove_connection(self, user_id: str):
        """
        Remove connection from pool and close it.
        
        Args:
            user_id: User/account ID
        """
        if user_id in self._connections:
            conn_data = self._connections[user_id]
            service = conn_data['service']
            
            # Close WebSocket connection
            try:
                if hasattr(service, 'close'):
                    service.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket for user {user_id}: {e}")
            
            # Remove from pool
            del self._connections[user_id]
    
    def _is_connection_healthy(self, service: WebSocketService) -> bool:
        """
        Check if a WebSocket connection is healthy.
        
        Args:
            service: WebSocketService instance
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check if WebSocket service has a connection
            if not hasattr(service, 'ws') or service.ws is None:
                return False
            
            # Check if connection is open (depends on websocket library)
            if hasattr(service.ws, 'open'):
                return service.ws.open
            elif hasattr(service.ws, 'connected'):
                return service.ws.connected
            
            # If we can't determine, assume healthy (optimistic)
            return True
            
        except Exception as e:
            logger.error(f"Error checking WebSocket health: {e}")
            return False
    
    def _evict_idle_connection(self):
        """
        Evict the least recently used idle connection to make room.
        """
        # Find idle connections sorted by last_used
        idle_connections = [
            (user_id, conn_data)
            for user_id, conn_data in self._connections.items()
            if not conn_data['in_use']
        ]
        
        if not idle_connections:
            # No idle connections, evict oldest connection regardless
            logger.warning("Pool full with no idle connections, evicting oldest")
            oldest_user_id = min(
                self._connections.keys(),
                key=lambda uid: self._connections[uid]['last_used']
            )
            self._remove_connection(oldest_user_id)
        else:
            # Evict least recently used idle connection
            lru_user_id = min(idle_connections, key=lambda x: x[1]['last_used'])[0]
            self._remove_connection(lru_user_id)
        
        self._stats['evictions'] += 1
        logger.info(f"Evicted connection from pool (evictions: {self._stats['evictions']})")
    
    def _health_check_loop(self):
        """
        Background thread that periodically checks connection health.
        Runs every 60 seconds.
        """
        while True:
            try:
                time.sleep(60)  # Check every minute
                self._perform_health_check()
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
    
    def _perform_health_check(self):
        """
        Check all connections for health and idle timeout.
        """
        with self._lock:
            current_time = time.time()
            user_ids_to_remove = []
            
            for user_id, conn_data in self._connections.items():
                # Skip connections currently in use
                if conn_data['in_use']:
                    continue
                
                # Check idle timeout
                idle_time = current_time - conn_data['last_used']
                if idle_time > self.idle_timeout:
                    logger.info(f"Connection for user {user_id} idle for {idle_time:.0f}s, removing")
                    user_ids_to_remove.append(user_id)
                    continue
                
                # Check connection health
                if not self._is_connection_healthy(conn_data['service']):
                    logger.warning(f"Connection for user {user_id} unhealthy, removing")
                    user_ids_to_remove.append(user_id)
            
            # Remove unhealthy/idle connections
            for user_id in user_ids_to_remove:
                self._remove_connection(user_id)
            
            self._stats['health_checks'] += 1
            
            if user_ids_to_remove:
                logger.info(
                    f"Health check completed: removed {len(user_ids_to_remove)} connections "
                    f"(pool size: {len(self._connections)})"
                )


# ============================================================================
# GLOBAL POOL INSTANCE
# ============================================================================
# Single global pool instance shared across the application
_websocket_pool: Optional[WebSocketPool] = None


def get_websocket_pool() -> WebSocketPool:
    """
    Get the global WebSocket pool instance (singleton pattern).
    
    Returns:
        WebSocketPool instance
    """
    global _websocket_pool
    if _websocket_pool is None:
        _websocket_pool = WebSocketPool(
            max_connections=100,  # Sufficient for 100-1000 concurrent users
            idle_timeout=300  # 5 minutes idle timeout
        )
    return _websocket_pool


def close_websocket_pool():
    """
    Close the global WebSocket pool (for shutdown).
    """
    global _websocket_pool
    if _websocket_pool is not None:
        _websocket_pool.close_all()
        _websocket_pool = None
