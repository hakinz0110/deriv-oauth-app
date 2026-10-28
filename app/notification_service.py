"""
Notification Service
Manages in-app notifications with Supabase persistence and smart polling architecture.

Senior Developer Implementation:
- Event-driven notification creation
- Efficient polling-friendly queries
- Type-based filtering
- Priority levels
- Mark as read/unread
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from flask import current_app
from app.supabase_service import SupabaseService


class NotificationService:
    """
    Handles notification creation, retrieval, and management.
    Designed for smart polling architecture (10-second intervals).
    """
    
    # Notification types
    TYPE_TRADE_OPENED = 'trade_opened'
    TYPE_TRADE_CLOSED = 'trade_closed'
    TYPE_BOT_STARTED = 'bot_started'
    TYPE_BOT_STOPPED = 'bot_stopped'
    TYPE_BOT_ERROR = 'bot_error'
    TYPE_DAILY_LOSS_LIMIT = 'daily_loss_limit'
    TYPE_STRATEGY_MILESTONE = 'strategy_milestone'
    TYPE_SYSTEM = 'system'
    
    # Priority levels
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    
    @classmethod
    def create_notification(cls, user_id: str, notification_type: str, 
                          title: str, message: str, 
                          priority: str = PRIORITY_NORMAL,
                          metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create a new notification.
        
        Args:
            user_id: User UUID
            notification_type: Notification type constant
            title: Short notification title
            message: Notification message
            priority: Priority level
            metadata: Additional data (trade_id, bot_id, etc.)
            
        Returns:
            dict: Created notification
        """
        try:
            supabase = SupabaseService.get_client()
            
            data = {
                'user_id': user_id,
                'type': notification_type,
                'title': title,
                'message': message,
                'priority': priority,
                'metadata': metadata or {},
                'is_read': False,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = supabase.table('notifications').insert(data).execute()
            
            if result.data:
                current_app.logger.info(f'Notification created: {notification_type} for user {user_id}')
                return result.data[0]
            
            return {}
            
        except Exception as e:
            current_app.logger.error(f'Failed to create notification: {str(e)}')
            return {}
    
    @classmethod
    def get_user_notifications(cls, user_id: str, limit: int = 20, 
                              unread_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get user notifications ordered by most recent.
        
        Args:
            user_id: User UUID
            limit: Max notifications to return
            unread_only: Only return unread notifications
            
        Returns:
            list: Notification objects
        """
        try:
            supabase = SupabaseService.get_client()
            
            query = supabase.table('notifications').select('*').eq('user_id', user_id)
            
            if unread_only:
                query = query.eq('is_read', False)
            
            result = query.order('created_at', desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            current_app.logger.error(f'Failed to get notifications: {str(e)}')
            return []
    
    @classmethod
    def get_unread_count(cls, user_id: str) -> int:
        """
        Get count of unread notifications.
        Optimized for polling - returns count only.
        
        Args:
            user_id: User UUID
            
        Returns:
            int: Count of unread notifications
        """
        try:
            supabase = SupabaseService.get_client()
            
            result = supabase.table('notifications').select(
                'id', count='exact'
            ).eq('user_id', user_id).eq('is_read', False).execute()
            
            return result.count if result.count else 0
            
        except Exception as e:
            current_app.logger.error(f'Failed to get unread count: {str(e)}')
            return 0
    
    @classmethod
    def mark_as_read(cls, notification_id: str, user_id: str) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: Notification UUID
            user_id: User UUID (for security)
            
        Returns:
            bool: Success status
        """
        try:
            supabase = SupabaseService.get_client()
            
            result = supabase.table('notifications').update({
                'is_read': True,
                'read_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', notification_id).eq('user_id', user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            current_app.logger.error(f'Failed to mark notification as read: {str(e)}')
            return False
    
    @classmethod
    def mark_all_as_read(cls, user_id: str) -> int:
        """
        Mark all notifications as read for user.
        
        Args:
            user_id: User UUID
            
        Returns:
            int: Number of notifications marked as read
        """
        try:
            supabase = SupabaseService.get_client()
            
            result = supabase.table('notifications').update({
                'is_read': True,
                'read_at': datetime.now(timezone.utc).isoformat()
            }).eq('user_id', user_id).eq('is_read', False).execute()
            
            count = len(result.data) if result.data else 0
            current_app.logger.info(f'Marked {count} notifications as read for user {user_id}')
            
            return count
            
        except Exception as e:
            current_app.logger.error(f'Failed to mark all as read: {str(e)}')
            return 0
    
    @classmethod
    def delete_notification(cls, notification_id: str, user_id: str) -> bool:
        """
        Delete a notification.
        
        Args:
            notification_id: Notification UUID
            user_id: User UUID (for security)
            
        Returns:
            bool: Success status
        """
        try:
            supabase = SupabaseService.get_client()
            
            result = supabase.table('notifications').delete().eq(
                'id', notification_id
            ).eq('user_id', user_id).execute()
            
            return len(result.data) > 0
            
        except Exception as e:
            current_app.logger.error(f'Failed to delete notification: {str(e)}')
            return False
    
    # ==================== NOTIFICATION TRIGGERS ====================
    
    @classmethod
    def notify_trade_opened(cls, user_id: str, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create notification for trade opened.
        
        Args:
            user_id: User UUID
            trade_data: Trade details
        """
        symbol = trade_data.get('symbol', 'Unknown')
        direction = trade_data.get('direction', 'CALL')
        stake = trade_data.get('stake', 0)
        
        title = f"Trade Opened: {symbol}"
        message = f"{direction} trade opened on {symbol} with ${stake:.2f} stake"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_TRADE_OPENED,
            title=title,
            message=message,
            priority=cls.PRIORITY_NORMAL,
            metadata={
                'trade_id': trade_data.get('contract_id'),
                'symbol': symbol,
                'direction': direction,
                'stake': float(stake)
            }
        )
    
    @classmethod
    def notify_trade_closed(cls, user_id: str, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create notification for trade closed.
        
        Args:
            user_id: User UUID
            trade_data: Trade details with outcome
        """
        symbol = trade_data.get('symbol', 'Unknown')
        outcome = trade_data.get('outcome', 'closed')
        pnl = float(trade_data.get('pnl', 0))
        
        # Determine priority and emoji based on outcome
        if outcome == 'win':
            emoji = '✅'
            priority = cls.PRIORITY_NORMAL
        elif outcome == 'loss':
            emoji = '❌'
            priority = cls.PRIORITY_NORMAL
        else:
            emoji = '⚖️'
            priority = cls.PRIORITY_LOW
        
        title = f"{emoji} Trade Closed: {outcome.title()}"
        
        sign = '+' if pnl >= 0 else ''
        message = f"{symbol} trade closed: {sign}${pnl:.2f} P&L"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_TRADE_CLOSED,
            title=title,
            message=message,
            priority=priority,
            metadata={
                'trade_id': trade_data.get('contract_id'),
                'symbol': symbol,
                'outcome': outcome,
                'pnl': pnl
            }
        )
    
    @classmethod
    def notify_bot_started(cls, user_id: str, bot_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create notification for bot started.
        
        Args:
            user_id: User UUID
            bot_data: Bot details
        """
        bot_name = bot_data.get('name', 'Trading Bot')
        systems_count = len(bot_data.get('active_trading_systems', []))
        
        title = "🤖 Bot Started"
        message = f"{bot_name} started with {systems_count} trading system(s)"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_BOT_STARTED,
            title=title,
            message=message,
            priority=cls.PRIORITY_NORMAL,
            metadata={
                'bot_id': bot_data.get('id'),
                'bot_name': bot_name,
                'systems_count': systems_count
            }
        )
    
    @classmethod
    def notify_bot_stopped(cls, user_id: str, bot_data: Dict[str, Any], 
                          reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Create notification for bot stopped.
        
        Args:
            user_id: User UUID
            bot_data: Bot details
            reason: Stop reason (optional)
        """
        bot_name = bot_data.get('name', 'Trading Bot')
        
        title = "⏸️ Bot Stopped"
        message = f"{bot_name} has been stopped"
        
        if reason:
            message += f": {reason}"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_BOT_STOPPED,
            title=title,
            message=message,
            priority=cls.PRIORITY_NORMAL,
            metadata={
                'bot_id': bot_data.get('id'),
                'bot_name': bot_name,
                'reason': reason
            }
        )
    
    @classmethod
    def notify_bot_error(cls, user_id: str, bot_data: Dict[str, Any], 
                        error_message: str) -> Dict[str, Any]:
        """
        Create notification for bot error.
        
        Args:
            user_id: User UUID
            bot_data: Bot details
            error_message: Error description
        """
        bot_name = bot_data.get('name', 'Trading Bot')
        
        title = "⚠️ Bot Error"
        message = f"{bot_name}: {error_message}"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_BOT_ERROR,
            title=title,
            message=message,
            priority=cls.PRIORITY_HIGH,
            metadata={
                'bot_id': bot_data.get('id'),
                'bot_name': bot_name,
                'error': error_message
            }
        )
    
    @classmethod
    def notify_daily_loss_limit(cls, user_id: str, loss_amount: float, 
                               limit_amount: float) -> Dict[str, Any]:
        """
        Create notification for daily loss limit reached.
        
        Args:
            user_id: User UUID
            loss_amount: Current loss amount
            limit_amount: Loss limit threshold
        """
        title = "🚨 Daily Loss Limit Reached"
        message = f"You've reached your daily loss limit: -${abs(loss_amount):.2f} / ${limit_amount:.2f}"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_DAILY_LOSS_LIMIT,
            title=title,
            message=message,
            priority=cls.PRIORITY_URGENT,
            metadata={
                'loss_amount': float(loss_amount),
                'limit_amount': float(limit_amount)
            }
        )
    
    @classmethod
    def notify_strategy_milestone(cls, user_id: str, milestone_type: str, 
                                  strategy_name: str, details: str) -> Dict[str, Any]:
        """
        Create notification for strategy performance milestone.
        
        Args:
            user_id: User UUID
            milestone_type: Type of milestone (e.g., 'win_streak')
            strategy_name: Strategy name
            details: Milestone details
        """
        title = f"🎯 Milestone: {milestone_type.replace('_', ' ').title()}"
        message = f"{strategy_name}: {details}"
        
        return cls.create_notification(
            user_id=user_id,
            notification_type=cls.TYPE_STRATEGY_MILESTONE,
            title=title,
            message=message,
            priority=cls.PRIORITY_LOW,
            metadata={
                'milestone_type': milestone_type,
                'strategy_name': strategy_name
            }
        )


class NotificationServiceError(Exception):
    """Custom exception for notification service errors"""
    
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert error to dictionary for JSON response"""
        return {
            'error': self.error_code,
            'message': self.message
        }
