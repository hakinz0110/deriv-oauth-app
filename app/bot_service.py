"""
Bot Service - State Management for Automated Trading Bot
=========================================================
Handles bot lifecycle, state persistence, and configuration management.
Each user has ONE bot that can manage multiple trading systems simultaneously.
"""

from app.supabase_service import SupabaseService
from datetime import datetime, timezone
import json


class BotService:
    """
    Service for managing trading bot state and configuration.
    
    Bot States:
        - inactive: Not running
        - starting: Initializing
        - running: Active trading
        - paused: Temporarily stopped
        - stopping: Gracefully shutting down
        - error: Exception occurred
    """
    
    @staticmethod
    def get_or_create_bot(user_id):
        """
        Get existing bot or create new one for user.
        Each user has exactly ONE bot.
        
        Args:
            user_id: User identifier
            
        Returns:
            dict: Bot record from database
        """
        supabase = SupabaseService.get_client()
        
        # Try to get existing bot
        result = supabase.table('bots')\
            .select('*')\
            .eq('user_id', user_id)\
            .limit(1)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        
        # Create new bot
        bot_data = {
            'user_id': user_id,
            'name': 'My Trading Bot',
            'status': 'inactive',
            'config': {
                'max_concurrent_trades': 3,
                'check_interval_seconds': 5,
                'enable_notifications': True,
                'auto_restart_on_error': False
            },
            'active_trading_systems': [],
            'current_positions': [],
            'statistics': {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_profit': 0,
                'uptime_seconds': 0,
                'errors_count': 0
            },
            'error_log': []
        }
        
        result = supabase.table('bots').insert(bot_data).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_bot_by_id(bot_id, user_id):
        """
        Get bot by ID with user verification.
        
        Args:
            bot_id: Bot UUID
            user_id: User identifier for verification
            
        Returns:
            dict: Bot record or None
        """
        supabase = SupabaseService.get_client()
        
        result = supabase.table('bots')\
            .select('*')\
            .eq('id', bot_id)\
            .eq('user_id', user_id)\
            .limit(1)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_bot_status(bot_id, status, error_message=None):
        """
        Update bot status.
        
        Args:
            bot_id: Bot UUID
            status: New status (inactive/starting/running/paused/stopping/error)
            error_message: Optional error message if status is 'error'
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        update_data = {'status': status}
        
        # Handle status-specific updates
        if status == 'running':
            update_data['started_at'] = datetime.now(timezone.utc).isoformat()
        elif status in ['inactive', 'stopped']:
            update_data['stopped_at'] = datetime.now(timezone.utc).isoformat()
            update_data['websocket_connected'] = False
        elif status == 'error':
            if error_message:
                update_data['last_error'] = error_message
                update_data['last_error_time'] = datetime.now(timezone.utc).isoformat()
        
        result = supabase.table('bots')\
            .update(update_data)\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_bot_config(bot_id, config):
        """
        Update bot configuration.
        
        Args:
            bot_id: Bot UUID
            config: Configuration dictionary
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        result = supabase.table('bots')\
            .update({'config': config})\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def set_active_trading_systems(bot_id, trading_system_ids):
        """
        Set which trading systems the bot should monitor.
        
        Args:
            bot_id: Bot UUID
            trading_system_ids: List of trading system UUIDs
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        result = supabase.table('bots')\
            .update({'active_trading_systems': trading_system_ids})\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_current_positions(bot_id, positions):
        """
        Update current open positions state.
        
        Args:
            bot_id: Bot UUID
            positions: List of position dictionaries
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        result = supabase.table('bots')\
            .update({
                'current_positions': positions,
                'last_check_time': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_websocket_status(bot_id, connected, heartbeat_time=None):
        """
        Update WebSocket connection status.
        
        Args:
            bot_id: Bot UUID
            connected: Boolean connection status
            heartbeat_time: Optional heartbeat timestamp
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        update_data = {'websocket_connected': connected}
        
        if heartbeat_time:
            update_data['last_heartbeat'] = heartbeat_time
        elif connected:
            update_data['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        
        result = supabase.table('bots')\
            .update(update_data)\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_statistics(bot_id, trade_outcome, profit):
        """
        Update bot statistics after a trade.
        
        Args:
            bot_id: Bot UUID
            trade_outcome: 'win' or 'loss'
            profit: Profit/loss amount (can be negative)
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        # Get current bot
        bot = BotService.get_bot_by_id(bot_id, None)  # Skip user check for internal call
        if not bot:
            return None
        
        stats = bot.get('statistics', {})
        
        # Update statistics
        stats['total_trades'] = stats.get('total_trades', 0) + 1
        stats['total_profit'] = stats.get('total_profit', 0) + profit
        
        if trade_outcome == 'win':
            stats['winning_trades'] = stats.get('winning_trades', 0) + 1
        else:
            stats['losing_trades'] = stats.get('losing_trades', 0) + 1
        
        result = supabase.table('bots')\
            .update({
                'statistics': stats,
                'last_trade_time': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def log_event(bot_id, user_id, log_level, message, event_type, 
                  trading_system_id=None, trade_id=None, context_data=None):
        """
        Log bot activity event.
        
        Args:
            bot_id: Bot UUID
            user_id: User identifier
            log_level: 'debug', 'info', 'warning', 'error', 'critical'
            message: Log message
            event_type: Event type (bot_start, bot_stop, trade_opened, etc.)
            trading_system_id: Optional trading system UUID
            trade_id: Optional trade UUID
            context_data: Optional additional context
            
        Returns:
            dict: Log record
        """
        supabase = SupabaseService.get_client()
        
        log_data = {
            'bot_id': bot_id,
            'user_id': user_id,
            'log_level': log_level,
            'message': message,
            'event_type': event_type,
            'context_data': context_data or {}
        }
        
        if trading_system_id:
            log_data['trading_system_id'] = trading_system_id
        
        if trade_id:
            log_data['trade_id'] = trade_id
        
        result = supabase.table('bot_logs').insert(log_data).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_bot_logs(bot_id, limit=100, event_type=None):
        """
        Get bot activity logs.
        
        Args:
            bot_id: Bot UUID
            limit: Maximum number of logs to return
            event_type: Optional filter by event type
            
        Returns:
            list: Log records
        """
        supabase = SupabaseService.get_client()
        
        query = supabase.table('bot_logs')\
            .select('*')\
            .eq('bot_id', bot_id)\
            .order('created_at', desc=True)\
            .limit(limit)
        
        if event_type:
            query = query.eq('event_type', event_type)
        
        result = query.execute()
        return result.data if result.data else []
    
    @staticmethod
    def add_error_to_log(bot_id, error_message, error_context=None):
        """
        Add error to bot's error log (maintains last 50 errors).
        
        Args:
            bot_id: Bot UUID
            error_message: Error message
            error_context: Optional error context data
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        # Get current bot
        result = supabase.table('bots')\
            .select('error_log, statistics')\
            .eq('id', bot_id)\
            .limit(1)\
            .execute()
        
        if not result.data:
            return None
        
        bot = result.data[0]
        error_log = bot.get('error_log', [])
        statistics = bot.get('statistics', {})
        
        # Add new error
        error_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': error_message,
            'context': error_context or {}
        }
        
        error_log.insert(0, error_entry)
        
        # Keep only last 50 errors
        error_log = error_log[:50]
        
        # Update error count in statistics
        statistics['errors_count'] = statistics.get('errors_count', 0) + 1
        
        # Update bot
        update_result = supabase.table('bots')\
            .update({
                'error_log': error_log,
                'statistics': statistics,
                'last_error': error_message,
                'last_error_time': datetime.now(timezone.utc).isoformat()
            })\
            .eq('id', bot_id)\
            .execute()
        
        return update_result.data[0] if update_result.data else None
    
    @staticmethod
    def clear_error_state(bot_id):
        """
        Clear bot error state (used when resuming after error).
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            dict: Updated bot record
        """
        supabase = SupabaseService.get_client()
        
        result = supabase.table('bots')\
            .update({
                'last_error': None,
                'last_error_time': None
            })\
            .eq('id', bot_id)\
            .execute()
        
        return result.data[0] if result.data else None


class BotServiceError(Exception):
    """Custom exception for bot service errors."""
    
    def __init__(self, message, error_code='BOT_ERROR'):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert error to dictionary for JSON response."""
        return {
            'error': self.error_code,
            'message': self.message
        }
