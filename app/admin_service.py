"""
Admin Service

Provides administrative functionality for platform monitoring and management.
Following best practices for single-user admin model without RBAC.

Features:
- Platform statistics and health metrics
- User management (view active users, activity)
- System monitoring (bot status, error tracking)
- Performance analytics across all users
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from flask import current_app

logger = logging.getLogger(__name__)


class AdminServiceError(Exception):
    """Base exception for AdminService errors."""
    
    def __init__(self, message: str, error_code: str = 'ADMIN_ERROR'):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self) -> dict:
        return {
            'error': self.error_code,
            'message': self.message
        }


class AdminService:
    """
    Administrative service for platform management.
    
    Best Practices:
    - Read-only operations for viewing data
    - No user modification (users self-manage via OAuth)
    - Focus on monitoring and observability
    - Performance metrics aggregation
    """
    
    @staticmethod
    def get_platform_statistics(timeframe: str = '24h') -> dict:
        """
        Get comprehensive platform statistics.
        
        Args:
            timeframe: '24h', '7d', '30d', 'all' (default: '24h')
            
        Returns:
            Dictionary with platform metrics
        """
        try:
            supabase = current_app.supabase
            
            # Calculate time filter
            time_filter = AdminService._calculate_time_filter(timeframe)
            
            # Total users (unique accounts that have traded)
            total_users_query = supabase.table('trades').select('user_id', count='exact').execute()
            unique_users = len(set([t['user_id'] for t in total_users_query.data])) if total_users_query.data else 0
            
            # Active users (traded in timeframe)
            active_users_query = supabase.table('trades').select('user_id').gte('opened_at', time_filter).execute()
            active_users = len(set([t['user_id'] for t in active_users_query.data])) if active_users_query.data else 0
            
            # Total trades
            total_trades_query = supabase.table('trades').select('*', count='exact').execute()
            total_trades = total_trades_query.count if hasattr(total_trades_query, 'count') else len(total_trades_query.data)
            
            # Trades in timeframe
            timeframe_trades_query = supabase.table('trades').select('*', count='exact').gte('opened_at', time_filter).execute()
            timeframe_trades = timeframe_trades_query.count if hasattr(timeframe_trades_query, 'count') else len(timeframe_trades_query.data)
            
            # Total bots
            bots_query = supabase.table('bots').select('*', count='exact').execute()
            total_bots = bots_query.count if hasattr(bots_query, 'count') else len(bots_query.data)
            
            # Running bots
            running_bots_query = supabase.table('bots').select('*', count='exact').eq('status', 'running').execute()
            running_bots = running_bots_query.count if hasattr(running_bots_query, 'count') else len(running_bots_query.data)
            
            # Trading systems
            systems_query = supabase.table('trading_systems').select('*', count='exact').execute()
            total_systems = systems_query.count if hasattr(systems_query, 'count') else len(systems_query.data)
            
            # Active trading systems
            active_systems_query = supabase.table('trading_systems').select('*', count='exact').eq('is_active', True).execute()
            active_systems = active_systems_query.count if hasattr(active_systems_query, 'count') else len(active_systems_query.data)
            
            # Platform P/L
            trades_data = supabase.table('trades').select('profit_loss').gte('opened_at', time_filter).execute()
            total_pnl = sum(float(t.get('profit_loss', 0) or 0) for t in trades_data.data) if trades_data.data else 0
            
            # Win rate
            winning_trades = sum(1 for t in trades_data.data if float(t.get('profit_loss', 0) or 0) > 0) if trades_data.data else 0
            win_rate = (winning_trades / len(trades_data.data) * 100) if trades_data.data and len(trades_data.data) > 0 else 0
            
            return {
                'timeframe': timeframe,
                'users': {
                    'total': unique_users,
                    'active': active_users,
                    'active_percentage': round((active_users / unique_users * 100) if unique_users > 0 else 0, 2)
                },
                'trades': {
                    'total': total_trades,
                    'timeframe': timeframe_trades,
                    'avg_per_user': round(timeframe_trades / active_users, 2) if active_users > 0 else 0
                },
                'bots': {
                    'total': total_bots,
                    'running': running_bots,
                    'running_percentage': round((running_bots / total_bots * 100) if total_bots > 0 else 0, 2)
                },
                'trading_systems': {
                    'total': total_systems,
                    'active': active_systems,
                    'avg_per_user': round(total_systems / unique_users, 2) if unique_users > 0 else 0
                },
                'performance': {
                    'total_pnl': round(total_pnl, 2),
                    'win_rate': round(win_rate, 2),
                    'avg_pnl_per_trade': round(total_pnl / timeframe_trades, 2) if timeframe_trades > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting platform statistics: {str(e)}")
            raise AdminServiceError(f"Failed to get platform statistics: {str(e)}", 'STATS_ERROR')
    
    @staticmethod
    def get_active_users(limit: int = 50, offset: int = 0) -> dict:
        """
        Get list of active users with recent activity.
        
        Args:
            limit: Number of users to return (default: 50)
            offset: Pagination offset (default: 0)
            
        Returns:
            Dictionary with user list and pagination info
        """
        try:
            supabase = current_app.supabase
            
            # Get users from trades (group by user_id)
            trades_query = supabase.table('trades').select('user_id, opened_at, profit_loss').order('opened_at', desc=True).execute()
            
            # Aggregate user data
            user_data = {}
            for trade in trades_query.data:
                user_id = trade['user_id']
                if user_id not in user_data:
                    user_data[user_id] = {
                        'user_id': user_id,
                        'total_trades': 0,
                        'total_pnl': 0,
                        'last_trade_at': None
                    }
                
                user_data[user_id]['total_trades'] += 1
                user_data[user_id]['total_pnl'] += float(trade.get('profit_loss', 0) or 0)
                
                # Track most recent trade
                trade_time = trade.get('opened_at')
                if trade_time and (not user_data[user_id]['last_trade_at'] or trade_time > user_data[user_id]['last_trade_at']):
                    user_data[user_id]['last_trade_at'] = trade_time
            
            # Convert to list and sort by last activity
            users_list = list(user_data.values())
            users_list.sort(key=lambda x: x['last_trade_at'] or '', reverse=True)
            
            # Paginate
            total_users = len(users_list)
            paginated_users = users_list[offset:offset + limit]
            
            # Get bot status for these users
            for user in paginated_users:
                bot_query = supabase.table('bots').select('status').eq('user_id', user['user_id']).execute()
                user['bot_status'] = bot_query.data[0]['status'] if bot_query.data else 'none'
                
                # Round P/L
                user['total_pnl'] = round(user['total_pnl'], 2)
            
            return {
                'users': paginated_users,
                'pagination': {
                    'total': total_users,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + limit < total_users
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting active users: {str(e)}")
            raise AdminServiceError(f"Failed to get active users: {str(e)}", 'USERS_ERROR')
    
    @staticmethod
    def get_system_health() -> dict:
        """
        Get system health metrics.
        
        Returns:
            Dictionary with health indicators
        """
        try:
            supabase = current_app.supabase
            
            # Check recent errors from audit logs (if table exists)
            try:
                last_hour = (datetime.utcnow() - timedelta(hours=1)).isoformat()
                errors_query = supabase.table('audit_logs').select('*', count='exact').eq('status', 'error').gte('created_at', last_hour).execute()
                recent_errors = errors_query.count if hasattr(errors_query, 'count') else len(errors_query.data)
            except Exception:
                recent_errors = 0  # Table doesn't exist or query failed
            
            # Check bot health
            bots_query = supabase.table('bots').select('status').execute()
            bot_statuses = {}
            for bot in bots_query.data:
                status = bot['status']
                bot_statuses[status] = bot_statuses.get(status, 0) + 1
            
            # Check database connectivity
            db_connected = True
            try:
                supabase.table('trades').select('id').limit(1).execute()
            except Exception:
                db_connected = False
            
            # Calculate health score (0-100)
            health_score = 100
            if recent_errors > 10:
                health_score -= 20
            elif recent_errors > 5:
                health_score -= 10
            
            if bot_statuses.get('error', 0) > 2:
                health_score -= 15
            
            if not db_connected:
                health_score -= 50
            
            # Determine status
            if health_score >= 90:
                status = 'healthy'
            elif health_score >= 70:
                status = 'degraded'
            elif health_score >= 50:
                status = 'warning'
            else:
                status = 'critical'
            
            return {
                'status': status,
                'health_score': health_score,
                'metrics': {
                    'database_connected': db_connected,
                    'recent_errors_1h': recent_errors,
                    'bot_statuses': bot_statuses
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            raise AdminServiceError(f"Failed to get system health: {str(e)}", 'HEALTH_ERROR')
    
    @staticmethod
    def get_recent_errors(limit: int = 50) -> dict:
        """
        Get recent error logs from audit_logs table.
        
        Args:
            limit: Number of errors to return (default: 50)
            
        Returns:
            Dictionary with error logs
        """
        try:
            supabase = current_app.supabase
            
            # Get recent errors
            errors_query = supabase.table('audit_logs').select('*').eq('status', 'error').order('created_at', desc=True).limit(limit).execute()
            
            errors = []
            for error in errors_query.data:
                errors.append({
                    'id': error.get('id'),
                    'user_id': error.get('user_id'),
                    'action_type': error.get('action_type'),
                    'action_subtype': error.get('action_subtype'),
                    'error_message': error.get('error_message'),
                    'details': error.get('details'),
                    'created_at': error.get('created_at')
                })
            
            return {
                'errors': errors,
                'total': len(errors)
            }
            
        except Exception as e:
            logger.error(f"Error getting recent errors: {str(e)}")
            # If audit_logs table doesn't exist, return empty
            return {'errors': [], 'total': 0}
    
    @staticmethod
    def get_top_performers(limit: int = 10) -> dict:
        """
        Get top performing users by P/L.
        
        Args:
            limit: Number of users to return (default: 10)
            
        Returns:
            Dictionary with top performers
        """
        try:
            supabase = current_app.supabase
            
            # Get all trades
            trades_query = supabase.table('trades').select('user_id, profit_loss').execute()
            
            # Aggregate by user
            user_pnl = {}
            for trade in trades_query.data:
                user_id = trade['user_id']
                pnl = float(trade.get('profit_loss', 0) or 0)
                
                if user_id not in user_pnl:
                    user_pnl[user_id] = {'user_id': user_id, 'total_pnl': 0, 'trade_count': 0}
                
                user_pnl[user_id]['total_pnl'] += pnl
                user_pnl[user_id]['trade_count'] += 1
            
            # Sort by P/L and take top N
            top_performers = sorted(user_pnl.values(), key=lambda x: x['total_pnl'], reverse=True)[:limit]
            
            # Round values
            for performer in top_performers:
                performer['total_pnl'] = round(performer['total_pnl'], 2)
                performer['avg_pnl_per_trade'] = round(performer['total_pnl'] / performer['trade_count'], 2)
            
            return {
                'top_performers': top_performers,
                'total': len(top_performers)
            }
            
        except Exception as e:
            logger.error(f"Error getting top performers: {str(e)}")
            raise AdminServiceError(f"Failed to get top performers: {str(e)}", 'PERFORMERS_ERROR')
    
    # ==================== PRIVATE HELPER METHODS ====================
    
    @staticmethod
    def _calculate_time_filter(timeframe: str) -> str:
        """
        Calculate ISO timestamp for timeframe filter.
        
        Args:
            timeframe: '24h', '7d', '30d', 'all'
            
        Returns:
            ISO timestamp string
        """
        if timeframe == 'all':
            # Start from 2020 (before Deriv launched)
            return '2020-01-01T00:00:00Z'
        elif timeframe == '24h':
            return (datetime.utcnow() - timedelta(hours=24)).isoformat() + 'Z'
        elif timeframe == '7d':
            return (datetime.utcnow() - timedelta(days=7)).isoformat() + 'Z'
        elif timeframe == '30d':
            return (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'
        else:
            # Default to 24h
            return (datetime.utcnow() - timedelta(hours=24)).isoformat() + 'Z'
