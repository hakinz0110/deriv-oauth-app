"""
HTS Trade - Risk Management Service
Handles user risk limits and real-time risk monitoring
"""

from typing import Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class RiskService:
    """Service for managing user risk limits and real-time risk monitoring"""
    
    def __init__(self, supabase_client):
        """
        Initialize risk service
        
        Args:
            supabase_client: Supabase client instance
        """
        self.supabase = supabase_client
    
    def get_risk_limits(self, user_id: str) -> Dict:
        """
        Get user risk limits (creates default if not exists)
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with risk limits
        """
        try:
            # Use helper function to get or create
            result = self.supabase.rpc(
                'get_or_create_risk_limits',
                {'p_user_id': user_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                return {
                    'status': 'success',
                    'limits': result.data[0]
                }
            else:
                raise Exception('Failed to retrieve risk limits')
                
        except Exception as e:
            logger.error(f"Error getting risk limits for user {user_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def save_risk_limits(self, user_id: str, limits: Dict) -> Dict:
        """
        Save or update user risk limits
        
        Args:
            user_id: User identifier
            limits: Dict containing risk limit values
            
        Returns:
            Dict with status and updated limits
        """
        try:
            # Validate limits
            validation_result = self._validate_limits(limits)
            if not validation_result['valid']:
                return {
                    'status': 'error',
                    'message': validation_result['message']
                }
            
            # Prepare update data
            update_data = {
                'user_id': user_id,
                **limits
            }
            
            # Upsert risk limits
            result = self.supabase.table('user_risk_limits').upsert(
                update_data,
                on_conflict='user_id'
            ).execute()
            
            if result.data:
                logger.info(f"Risk limits updated for user {user_id}")
                return {
                    'status': 'success',
                    'limits': result.data[0]
                }
            else:
                raise Exception('Failed to save risk limits')
                
        except Exception as e:
            logger.error(f"Error saving risk limits for user {user_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _validate_limits(self, limits: Dict) -> Dict:
        """
        Validate risk limit values
        
        Args:
            limits: Dict containing risk limit values
            
        Returns:
            Dict with validation result
        """
        try:
            # Max daily loss must be positive
            if 'max_daily_loss' in limits:
                if Decimal(str(limits['max_daily_loss'])) <= 0:
                    return {'valid': False, 'message': 'Max daily loss must be positive'}
            
            # Max daily profit must be positive if set
            if 'max_daily_profit' in limits and limits['max_daily_profit'] is not None:
                if Decimal(str(limits['max_daily_profit'])) <= 0:
                    return {'valid': False, 'message': 'Max daily profit must be positive'}
            
            # Min stake must be positive
            if 'min_stake' in limits:
                if Decimal(str(limits['min_stake'])) <= 0:
                    return {'valid': False, 'message': 'Min stake must be positive'}
            
            # Max stake must be >= min stake
            if 'max_stake' in limits and 'min_stake' in limits:
                if Decimal(str(limits['max_stake'])) < Decimal(str(limits['min_stake'])):
                    return {'valid': False, 'message': 'Max stake must be >= min stake'}
            
            # Max stake percentage must be between 0 and 100
            if 'max_stake_percentage' in limits:
                percentage = Decimal(str(limits['max_stake_percentage']))
                if percentage <= 0 or percentage > 100:
                    return {'valid': False, 'message': 'Max stake percentage must be between 0 and 100'}
            
            # Max concurrent trades must be positive
            if 'max_concurrent_trades' in limits:
                if int(limits['max_concurrent_trades']) <= 0:
                    return {'valid': False, 'message': 'Max concurrent trades must be positive'}
            
            # Max open positions must be >= max concurrent trades
            if 'max_open_positions' in limits and 'max_concurrent_trades' in limits:
                if int(limits['max_open_positions']) < int(limits['max_concurrent_trades']):
                    return {'valid': False, 'message': 'Max open positions must be >= max concurrent trades'}
            
            # Max trades per hour must be positive
            if 'max_trades_per_hour' in limits:
                if int(limits['max_trades_per_hour']) <= 0:
                    return {'valid': False, 'message': 'Max trades per hour must be positive'}
            
            # Max trades per day must be >= max trades per hour
            if 'max_trades_per_day' in limits and 'max_trades_per_hour' in limits:
                if int(limits['max_trades_per_day']) < int(limits['max_trades_per_hour']):
                    return {'valid': False, 'message': 'Max trades per day must be >= max trades per hour'}
            
            # Cooldown must be >= 0
            if 'cooldown_after_loss_seconds' in limits:
                if int(limits['cooldown_after_loss_seconds']) < 0:
                    return {'valid': False, 'message': 'Cooldown must be >= 0'}
            
            # Consecutive losses must be positive if set
            if 'stop_on_consecutive_losses' in limits and limits['stop_on_consecutive_losses'] is not None:
                if int(limits['stop_on_consecutive_losses']) <= 0:
                    return {'valid': False, 'message': 'Stop on consecutive losses must be positive'}
            
            return {'valid': True}
            
        except (ValueError, TypeError) as e:
            return {'valid': False, 'message': f'Invalid limit value: {str(e)}'}
    
    def is_trading_allowed(self, user_id: str) -> Tuple[bool, str]:
        """
        Check if user is allowed to place new trades based on risk limits
        
        Args:
            user_id: User identifier
            
        Returns:
            Tuple (allowed: bool, reason: str)
        """
        try:
            # Use database function for comprehensive check
            result = self.supabase.rpc(
                'is_trading_allowed',
                {'p_user_id': user_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                check = result.data[0]
                return (check['allowed'], check['reason'])
            else:
                # If no data, assume allowed (fail-safe)
                return (True, 'No risk limits set')
                
        except Exception as e:
            logger.error(f"Error checking trading allowed for user {user_id}: {str(e)}")
            # Fail-safe: allow trading if check fails
            return (True, f'Risk check error: {str(e)}')
    
    def validate_trade_against_limits(self, user_id: str, stake: Decimal, balance: Decimal) -> Dict:
        """
        Validate a proposed trade against risk limits
        
        Args:
            user_id: User identifier
            stake: Proposed trade stake amount
            balance: Current account balance
            
        Returns:
            Dict with validation result
        """
        try:
            # Check if trading is allowed
            allowed, reason = self.is_trading_allowed(user_id)
            if not allowed:
                return {
                    'valid': False,
                    'message': reason
                }
            
            # Get risk limits
            limits_result = self.get_risk_limits(user_id)
            if limits_result['status'] != 'success':
                return {
                    'valid': False,
                    'message': 'Failed to retrieve risk limits'
                }
            
            limits = limits_result['limits']
            
            # Check min stake
            if stake < Decimal(str(limits['min_stake'])):
                return {
                    'valid': False,
                    'message': f"Stake below minimum: ${limits['min_stake']}"
                }
            
            # Check max stake
            if stake > Decimal(str(limits['max_stake'])):
                return {
                    'valid': False,
                    'message': f"Stake exceeds maximum: ${limits['max_stake']}"
                }
            
            # Check max stake percentage
            max_percentage_amount = balance * (Decimal(str(limits['max_stake_percentage'])) / 100)
            if stake > max_percentage_amount:
                return {
                    'valid': False,
                    'message': f"Stake exceeds {limits['max_stake_percentage']}% of balance"
                }
            
            # All checks passed
            return {
                'valid': True,
                'message': 'Trade validated successfully'
            }
            
        except Exception as e:
            logger.error(f"Error validating trade for user {user_id}: {str(e)}")
            return {
                'valid': False,
                'message': f'Validation error: {str(e)}'
            }
    
    def check_daily_loss_limit(self, user_id: str) -> Dict:
        """
        Check if daily loss limit has been reached
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with check result
        """
        try:
            # Get today's tracking
            tracking_result = self.supabase.rpc(
                'get_or_create_daily_tracking',
                {'p_user_id': user_id}
            ).execute()
            
            if not tracking_result.data or len(tracking_result.data) == 0:
                return {
                    'limit_reached': False,
                    'current_loss': 0,
                    'limit': 0
                }
            
            tracking = tracking_result.data[0]
            
            # Get risk limits
            limits_result = self.get_risk_limits(user_id)
            if limits_result['status'] != 'success':
                return {
                    'limit_reached': False,
                    'message': 'Failed to retrieve risk limits'
                }
            
            limits = limits_result['limits']
            
            # Check if loss limit reached
            current_loss = abs(min(Decimal(str(tracking['realized_pnl'])), Decimal('0')))
            max_loss = Decimal(str(limits['max_daily_loss']))
            limit_reached = current_loss >= max_loss
            
            # Create notification if limit just reached
            if limit_reached and limits['stop_on_daily_loss']:
                from app.notification_service import NotificationService
                NotificationService.notify_daily_loss_limit(
                    user_id=user_id,
                    loss_amount=float(current_loss),
                    limit_amount=float(max_loss)
                )
            
            return {
                'limit_reached': limit_reached,
                'current_loss': float(current_loss),
                'limit': float(max_loss),
                'remaining': float(max_loss - current_loss) if not limit_reached else 0,
                'stop_on_limit': limits['stop_on_daily_loss']
            }
            
        except Exception as e:
            logger.error(f"Error checking daily loss limit for user {user_id}: {str(e)}")
            return {
                'limit_reached': False,
                'message': f'Check error: {str(e)}'
            }
    
    def get_daily_tracking(self, user_id: str) -> Dict:
        """
        Get today's risk tracking statistics
        
        Args:
            user_id: User identifier
            
        Returns:
            Dict with tracking statistics
        """
        try:
            result = self.supabase.rpc(
                'get_or_create_daily_tracking',
                {'p_user_id': user_id}
            ).execute()
            
            if result.data and len(result.data) > 0:
                return {
                    'status': 'success',
                    'tracking': result.data[0]
                }
            else:
                raise Exception('Failed to retrieve daily tracking')
                
        except Exception as e:
            logger.error(f"Error getting daily tracking for user {user_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def update_tracking_after_trade(self, user_id: str, trade_result: Dict) -> Dict:
        """
        Update daily tracking after a trade completes
        
        Args:
            user_id: User identifier
            trade_result: Dict containing trade outcome (profit, loss, etc.)
            
        Returns:
            Dict with update status
        """
        try:
            # Get current tracking
            tracking_result = self.get_daily_tracking(user_id)
            if tracking_result['status'] != 'success':
                return tracking_result
            
            tracking = tracking_result['tracking']
            
            # Calculate updates
            pnl = Decimal(str(trade_result.get('profit', 0)))
            is_loss = pnl < 0
            
            # Update values
            updates = {
                'trades_today': tracking['trades_today'] + 1,
                'realized_pnl': Decimal(str(tracking['realized_pnl'])) + pnl,
                'last_trade_at': datetime.utcnow().isoformat()
            }
            
            # Update consecutive losses
            if is_loss:
                updates['consecutive_losses'] = tracking['consecutive_losses'] + 1
                updates['last_loss_at'] = datetime.utcnow().isoformat()
                updates['is_in_cooldown'] = True
                
                # Track largest loss
                if abs(pnl) > Decimal(str(tracking.get('largest_loss', 0))):
                    updates['largest_loss'] = abs(pnl)
            else:
                # Reset consecutive losses on win
                updates['consecutive_losses'] = 0
                updates['is_in_cooldown'] = False
            
            # Update in database
            result = self.supabase.table('daily_risk_tracking').update(updates).eq(
                'id', tracking['id']
            ).execute()
            
            if result.data:
                logger.info(f"Daily tracking updated for user {user_id}")
                return {
                    'status': 'success',
                    'tracking': result.data[0]
                }
            else:
                raise Exception('Failed to update tracking')
                
        except Exception as e:
            logger.error(f"Error updating tracking for user {user_id}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
