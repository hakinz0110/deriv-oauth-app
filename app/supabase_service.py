"""
Supabase Database Service - Matches existing HTS Trade schema
Handles persistent storage using your existing Supabase tables
"""
import os
from supabase import create_client, Client
from flask import current_app
from typing import Optional, Dict, Any, List
import json
from datetime import datetime
import uuid

class SupabaseService:
    """
    Manages Supabase database operations for HTS Trade app
    Uses your existing schema: users, sessions, bots, trades, etc.
    """
    
    _client: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client singleton"""
        if cls._client is None:
            url = os.environ.get('SUPABASE_URL')
            key = os.environ.get('SUPABASE_ANON_KEY')
            
            if not url or not key:
                raise SupabaseServiceError(
                    'Supabase credentials not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY to .env',
                    'MISSING_CREDENTIALS'
                )
            
            cls._client = create_client(url, key)
            current_app.logger.info('Supabase client initialized')
        
        return cls._client
    
    # ==================== USER MANAGEMENT ====================
    
    @classmethod
    def upsert_user(cls, user_id: str, email: str, deriv_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create or update user record
        
        Args:
            user_id: User UUID (from Supabase Auth or generated)
            email: User email
            deriv_data: Deriv account data (access_token, account_id, scopes, etc.)
        """
        try:
            supabase = cls.get_client()
            
            data = {
                'id': user_id,
                'email': email,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            if deriv_data:
                data.update({
                    'deriv_account_id': deriv_data.get('account_id'),
                    'deriv_access_token': deriv_data.get('access_token'),
                    'deriv_token_expires_at': deriv_data.get('expires_at'),
                    'deriv_scopes': deriv_data.get('scopes', [])
                })
            
            result = supabase.table('users').upsert(data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            current_app.logger.error(f'Failed to upsert user: {str(e)}')
            raise SupabaseServiceError('Failed to save user', 'USER_SAVE_FAILED')
    
    # ==================== SESSION MANAGEMENT ====================
    
    @classmethod
    def save_session(cls, session_id: str, user_id: str, access_token: str, 
                     account_data: Dict[str, Any], expires_at: datetime) -> Dict[str, Any]:
        """
        Save or update session (uses your existing sessions table)
        
        Args:
            session_id: Flask session ID
            user_id: User identifier (can be Deriv loginid or user UUID)
            access_token: OAuth access token
            account_data: Selected account information
            expires_at: Session expiration timestamp
        """
        try:
            supabase = cls.get_client()
            
            data = {
                'session_id': session_id,
                'user_id': user_id,
                'access_token': access_token,
                'selected_account_id': account_data.get('account_id'),
                'account_data': account_data,
                'expires_at': expires_at.isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('sessions').upsert(
                data,
                on_conflict='session_id'
            ).execute()
            
            current_app.logger.info(f'Session saved: {session_id}')
            return result.data[0] if result.data else {}
            
        except Exception as e:
            current_app.logger.error(f'Failed to save session: {str(e)}')
            raise SupabaseServiceError('Failed to save session', 'SESSION_SAVE_FAILED')
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session by session_id"""
        try:
            supabase = cls.get_client()
            
            result = supabase.table('sessions').select('*').eq(
                'session_id', session_id
            ).single().execute()
            
            return result.data if result.data else None
            
        except Exception as e:
            current_app.logger.debug(f'Session not found: {session_id}')
            return None
    
    @classmethod
    def delete_session(cls, session_id: str):
        """Delete session"""
        try:
            supabase = cls.get_client()
            supabase.table('sessions').delete().eq('session_id', session_id).execute()
            current_app.logger.info(f'Session deleted: {session_id}')
        except Exception as e:
            current_app.logger.error(f'Failed to delete session: {str(e)}')
    
    # ==================== BOT MANAGEMENT ====================
    
    @classmethod
    def get_user_bots(cls, user_id: str) -> List[Dict[str, Any]]:
        """Get all bots for a user"""
        try:
            supabase = cls.get_client()
            
            result = supabase.table('bots').select('*').eq(
                'user_id', user_id
            ).order('updated_at', desc=True).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            current_app.logger.error(f'Failed to get bots: {str(e)}')
            return []
    
    @classmethod
    def get_active_bot(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Get currently active bot for user"""
        try:
            supabase = cls.get_client()
            
            result = supabase.table('bots').select('*').eq(
                'user_id', user_id
            ).eq('is_active', True).eq(
                'status', 'running'
            ).single().execute()
            
            return result.data if result.data else None
            
        except Exception as e:
            return None
    
    # ==================== TRADE MANAGEMENT ====================
    
    @classmethod
    def save_trade(cls, user_id: str, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save trade to database (uses your existing trades table)
        
        Args:
            user_id: User UUID
            trade_data: Trade details from Deriv API
        """
        try:
            supabase = cls.get_client()
            
            data = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'bot_id': trade_data.get('bot_id'),
                'signal_id': trade_data.get('signal_id'),
                'direction': trade_data.get('direction', 'CALL'),
                'symbol': trade_data.get('symbol'),
                'contract_type': trade_data.get('contract_type'),
                'stake': float(trade_data.get('stake', 0)),
                'entry_price': float(trade_data.get('entry_price', 0)) if trade_data.get('entry_price') else None,
                'exit_price': float(trade_data.get('exit_price', 0)) if trade_data.get('exit_price') else None,
                'duration_seconds': trade_data.get('duration_seconds'),
                'take_profit': float(trade_data.get('take_profit', 0)) if trade_data.get('take_profit') else None,
                'stop_loss': float(trade_data.get('stop_loss', 0)) if trade_data.get('stop_loss') else None,
                'outcome': trade_data.get('outcome', 'open'),
                'pnl': float(trade_data.get('pnl', 0)),
                'pnl_percentage': float(trade_data.get('pnl_percentage', 0)) if trade_data.get('pnl_percentage') else None,
                'deriv_contract_id': trade_data.get('contract_id'),
                'deriv_transaction_id': trade_data.get('transaction_id'),
                'is_manual': trade_data.get('is_manual', False),
                'notes': trade_data.get('notes'),
                'opened_at': trade_data.get('opened_at', datetime.utcnow().isoformat()),
                'closed_at': trade_data.get('closed_at'),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = supabase.table('trades').insert(data).execute()
            
            current_app.logger.info(f'Trade saved: {data["id"]}')
            return result.data[0] if result.data else {}
            
        except Exception as e:
            current_app.logger.error(f'Failed to save trade: {str(e)}')
            raise SupabaseServiceError('Failed to save trade', 'TRADE_SAVE_FAILED')
    
    @classmethod
    def get_user_trades(cls, user_id: str, limit: int = 50, 
                       outcome: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get trades for a user
        
        Args:
            user_id: User UUID
            limit: Maximum trades to return
            outcome: Filter by outcome (open, win, loss)
        """
        try:
            supabase = cls.get_client()
            
            query = supabase.table('trades').select('*').eq('user_id', user_id)
            
            if outcome:
                query = query.eq('outcome', outcome)
            
            result = query.order('opened_at', desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            current_app.logger.error(f'Failed to get trades: {str(e)}')
            return []
    
    @classmethod
    def get_open_trades(cls, user_id: str) -> List[Dict[str, Any]]:
        """Get currently open trades"""
        return cls.get_user_trades(user_id, limit=100, outcome='open')
    
    # ==================== USER PREFERENCES ====================
    
    @classmethod
    def get_user_preferences(cls, user_id: str) -> Dict[str, Any]:
        """Get user preferences"""
        try:
            supabase = cls.get_client()
            
            result = supabase.table('user_preferences').select('*').eq(
                'user_id', user_id
            ).single().execute()
            
            return result.data if result.data else {}
            
        except Exception as e:
            # Return defaults if no preferences exist
            return {
                'default_stake': 10.00,
                'default_duration_seconds': 60,
                'auto_trade_enabled': False,
                'notifications_enabled': True,
                'theme': 'dark',
                'language': 'en',
                'currency': 'USD'
            }
    
    # ==================== NOTIFICATIONS ====================
    
    @classmethod
    def create_notification(cls, user_id: str, title: str, message: str, 
                          notification_type: str = 'info', priority: str = 'normal') -> Dict[str, Any]:
        """Create a notification for user"""
        try:
            supabase = cls.get_client()
            
            data = {
                'user_id': user_id,
                'type': notification_type,
                'title': title,
                'message': message,
                'priority': priority,
                'is_read': False
            }
            
            result = supabase.table('notifications').insert(data).execute()
            return result.data[0] if result.data else {}
            
        except Exception as e:
            current_app.logger.error(f'Failed to create notification: {str(e)}')
            return {}
    
    # ==================== ANALYTICS ====================
    
    @classmethod
    def log_analytics_event(cls, user_id: str, event_name: str, 
                          event_category: str = None, event_data: Dict = None, 
                          screen_name: str = None, session_id: str = None):
        """Log analytics event"""
        try:
            supabase = cls.get_client()
            
            data = {
                'user_id': user_id,
                'event_name': event_name,
                'event_category': event_category,
                'event_data': event_data or {},
                'screen_name': screen_name,
                'session_id': session_id
            }
            
            supabase.table('analytics_events').insert(data).execute()
            
        except Exception as e:
            current_app.logger.debug(f'Analytics event failed: {str(e)}')
            # Don't raise - analytics failures shouldn't break app
            pass


class SupabaseServiceError(Exception):
    """Custom exception for Supabase service errors"""
    
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
