"""
Trading System Service - CRUD operations for trading systems
Combines: Trade Parameters + Entry Strategy + Position Sizing + Exit Strategy
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal
import logging

from app.supabase_service import supabase
from app.errors import ValidationError, ConfigurationError
from app.entry_strategy_service import EntryStrategyService

logger = logging.getLogger(__name__)


class TradingSystemService:
    """Service for managing complete trading systems"""
    
    SUPPORTED_POSITION_SIZING = [
        'fixed',
        'martingale',
        'anti_martingale',
        'compound',
        'fibonacci',
        'dalembert'
    ]
    
    SUPPORTED_EXIT_STRATEGIES = [
        'time_based',
        'stop_loss_take_profit',
        'indicator_based'
    ]
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def create_trading_system(
        self,
        name: str,
        description: str,
        contract_type: str,
        symbol: str,
        duration: int,
        duration_unit: str,
        entry_strategy_type: str,
        entry_conditions: Dict[str, Any],
        entry_logic: str,
        position_sizing_type: str,
        position_sizing_config: Dict[str, Any],
        exit_strategy_type: str,
        exit_conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new trading system
        
        Args:
            name: System name
            description: System description
            contract_type: 'CALL', 'PUT', etc.
            symbol: 'R_100', 'BOOM500', etc.
            duration: Contract duration (e.g., 5, 60)
            duration_unit: 't', 's', 'm', 'h', 'd'
            entry_strategy_type: 'manual', 'rsi', 'macd', etc.
            entry_conditions: Entry rules configuration
            entry_logic: 'all' (AND) or 'any' (OR)
            position_sizing_type: 'fixed', 'martingale', etc.
            position_sizing_config: Position sizing parameters
            exit_strategy_type: 'time_based', 'stop_loss_take_profit', etc.
            exit_conditions: Exit rules configuration
        
        Returns:
            Created trading system dictionary
        """
        # Validate all configurations
        self._validate_trade_parameters(contract_type, symbol, duration, duration_unit)
        self._validate_entry_strategy(entry_strategy_type, entry_conditions)
        self._validate_position_sizing(position_sizing_type, position_sizing_config)
        self._validate_exit_strategy(exit_strategy_type, exit_conditions)
        
        # Apply defaults to position sizing config
        position_sizing_config = self._apply_position_sizing_defaults(
            position_sizing_type,
            position_sizing_config
        )
        
        # Apply defaults to entry conditions if needed
        if not entry_conditions:
            entry_conditions = {'rules': [], 'type': entry_strategy_type}
        
        # Create trading system
        trading_system_data = {
            'user_id': self.user_id,
            'name': name,
            'description': description,
            'is_active': False,
            
            # Trade parameters
            'contract_type': contract_type,
            'symbol': symbol,
            'duration': duration,
            'duration_unit': duration_unit,
            
            # Entry strategy
            'entry_strategy_type': entry_strategy_type,
            'entry_conditions': entry_conditions,
            'entry_logic': entry_logic,
            
            # Position sizing
            'position_sizing_type': position_sizing_type,
            'position_sizing_config': position_sizing_config,
            
            # Exit strategy
            'exit_strategy_type': exit_strategy_type,
            'exit_conditions': exit_conditions,
            
            # Stats (initialized to 0)
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.00,
            'total_profit': 0.00
        }
        
        try:
            result = supabase.table('trading_systems').insert(trading_system_data).execute()
            
            if result.data:
                logger.info(f"Created trading system: {result.data[0]['id']}")
                return result.data[0]
            else:
                raise ConfigurationError("Failed to create trading system")
                
        except Exception as e:
            logger.error(f"Error creating trading system: {e}")
            raise ConfigurationError(f"Failed to create trading system: {str(e)}")
    
    def get_user_trading_systems(self) -> List[Dict[str, Any]]:
        """Get all trading systems for the current user"""
        try:
            result = supabase.table('trading_systems')\
                .select('*')\
                .eq('user_id', self.user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error fetching trading systems: {e}")
            return []
    
    def get_trading_system(self, trading_system_id: str) -> Optional[Dict[str, Any]]:
        """Get a single trading system by ID"""
        try:
            result = supabase.table('trading_systems')\
                .select('*')\
                .eq('id', trading_system_id)\
                .eq('user_id', self.user_id)\
                .single()\
                .execute()
            
            return result.data
            
        except Exception as e:
            logger.error(f"Error fetching trading system: {e}")
            return None
    
    def update_trading_system(
        self,
        trading_system_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update a trading system
        
        Args:
            trading_system_id: System ID
            updates: Dictionary of fields to update
        
        Returns:
            Updated trading system or None
        """
        # Validate updates if they include critical fields
        if 'position_sizing_config' in updates:
            # Get current system to validate against its type
            current = self.get_trading_system(trading_system_id)
            if current:
                position_sizing_type = updates.get('position_sizing_type', current['position_sizing_type'])
                self._validate_position_sizing(position_sizing_type, updates['position_sizing_config'])
        
        if 'entry_conditions' in updates:
            current = self.get_trading_system(trading_system_id)
            if current:
                entry_strategy_type = updates.get('entry_strategy_type', current['entry_strategy_type'])
                self._validate_entry_strategy(entry_strategy_type, updates['entry_conditions'])
        
        try:
            result = supabase.table('trading_systems')\
                .update(updates)\
                .eq('id', trading_system_id)\
                .eq('user_id', self.user_id)\
                .execute()
            
            if result.data:
                logger.info(f"Updated trading system: {trading_system_id}")
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error updating trading system: {e}")
            return None
    
    def delete_trading_system(self, trading_system_id: str) -> bool:
        """Delete a trading system"""
        try:
            result = supabase.table('trading_systems')\
                .delete()\
                .eq('id', trading_system_id)\
                .eq('user_id', self.user_id)\
                .execute()
            
            logger.info(f"Deleted trading system: {trading_system_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting trading system: {e}")
            return False
    
    def activate_trading_system(self, trading_system_id: str) -> Optional[Dict[str, Any]]:
        """Activate a trading system"""
        return self.update_trading_system(trading_system_id, {'is_active': True})
    
    def deactivate_trading_system(self, trading_system_id: str) -> Optional[Dict[str, Any]]:
        """Deactivate a trading system"""
        return self.update_trading_system(trading_system_id, {'is_active': False})
    
    def add_rule(
        self,
        trading_system_id: str,
        rule_type: str,
        conditions: Dict[str, Any],
        actions: Dict[str, Any],
        priority: int = 0,
        is_enabled: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Add a custom rule to a trading system
        
        Args:
            trading_system_id: System ID
            rule_type: 'entry', 'exit', 'risk_management'
            conditions: Rule conditions
            actions: Actions to take
            priority: Execution priority (higher = first)
            is_enabled: Whether rule is active
        
        Returns:
            Created rule or None
        """
        # Verify trading system exists and belongs to user
        trading_system = self.get_trading_system(trading_system_id)
        if not trading_system:
            return None
        
        rule_data = {
            'trading_system_id': trading_system_id,
            'rule_type': rule_type,
            'conditions': conditions,
            'actions': actions,
            'priority': priority,
            'is_enabled': is_enabled
        }
        
        try:
            result = supabase.table('trading_system_rules')\
                .insert(rule_data)\
                .execute()
            
            if result.data:
                logger.info(f"Added rule to trading system: {trading_system_id}")
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Error adding rule: {e}")
            return None
    
    def get_trading_system_rules(self, trading_system_id: str) -> List[Dict[str, Any]]:
        """Get all rules for a trading system"""
        try:
            result = supabase.table('trading_system_rules')\
                .select('*')\
                .eq('trading_system_id', trading_system_id)\
                .order('priority', desc=True)\
                .execute()
            
            return result.data or []
            
        except Exception as e:
            logger.error(f"Error fetching rules: {e}")
            return []
    
    def _validate_trade_parameters(
        self,
        contract_type: str,
        symbol: str,
        duration: int,
        duration_unit: str
    ):
        """Validate trade parameters"""
        if not contract_type or not isinstance(contract_type, str):
            raise ValidationError("Valid contract_type is required")
        
        if not symbol or not isinstance(symbol, str):
            raise ValidationError("Valid symbol is required")
        
        if not isinstance(duration, int) or duration <= 0:
            raise ValidationError("Duration must be a positive integer")
        
        if duration_unit not in ['t', 's', 'm', 'h', 'd']:
            raise ValidationError("duration_unit must be one of: t, s, m, h, d")
    
    def _validate_entry_strategy(
        self,
        entry_strategy_type: str,
        entry_conditions: Dict[str, Any]
    ):
        """Validate entry strategy configuration"""
        if entry_strategy_type not in EntryStrategyService.SUPPORTED_STRATEGIES:
            raise ValidationError(f"Unsupported entry strategy: {entry_strategy_type}")
        
        # Validate entry conditions using EntryStrategyService
        is_valid, error_msg = EntryStrategyService.validate_entry_conditions(
            entry_strategy_type,
            entry_conditions
        )
        
        if not is_valid:
            raise ValidationError(f"Invalid entry conditions: {error_msg}")
    
    def _validate_position_sizing(
        self,
        position_sizing_type: str,
        config: Dict[str, Any]
    ):
        """Validate position sizing configuration"""
        if position_sizing_type not in self.SUPPORTED_POSITION_SIZING:
            raise ValidationError(f"Unsupported position sizing type: {position_sizing_type}")
        
        if not config or not isinstance(config, dict):
            raise ValidationError("position_sizing_config must be a valid dictionary")
        
        # Validate base_stake exists for all types
        if 'base_stake' not in config:
            raise ValidationError("base_stake is required in position_sizing_config")
        
        base_stake = config['base_stake']
        if not isinstance(base_stake, (int, float, Decimal)) or base_stake <= 0:
            raise ValidationError("base_stake must be a positive number")
        
        # Type-specific validation
        if position_sizing_type == 'martingale':
            if 'loss_multiplier' in config:
                if config['loss_multiplier'] <= 1:
                    raise ValidationError("loss_multiplier must be greater than 1")
        
        elif position_sizing_type == 'anti_martingale':
            if 'win_multiplier' in config:
                if config['win_multiplier'] <= 1:
                    raise ValidationError("win_multiplier must be greater than 1")
        
        elif position_sizing_type == 'compound':
            if 'profit_percentage' in config:
                if not 0 < config['profit_percentage'] <= 100:
                    raise ValidationError("profit_percentage must be between 0 and 100")
        
        # Validate max_stake if present
        if 'max_stake' in config:
            if config['max_stake'] < base_stake:
                raise ValidationError("max_stake must be greater than or equal to base_stake")
    
    def _validate_exit_strategy(
        self,
        exit_strategy_type: str,
        exit_conditions: Dict[str, Any]
    ):
        """Validate exit strategy configuration"""
        if exit_strategy_type not in self.SUPPORTED_EXIT_STRATEGIES:
            raise ValidationError(f"Unsupported exit strategy: {exit_strategy_type}")
        
        if not isinstance(exit_conditions, dict):
            raise ValidationError("exit_conditions must be a dictionary")
        
        # Validate stop_loss and take_profit if present
        if 'stop_loss' in exit_conditions:
            if not isinstance(exit_conditions['stop_loss'], (int, float, Decimal)) or exit_conditions['stop_loss'] <= 0:
                raise ValidationError("stop_loss must be a positive number")
        
        if 'take_profit' in exit_conditions:
            if not isinstance(exit_conditions['take_profit'], (int, float, Decimal)) or exit_conditions['take_profit'] <= 0:
                raise ValidationError("take_profit must be a positive number")
    
    def _apply_position_sizing_defaults(
        self,
        position_sizing_type: str,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply default values for position sizing configuration"""
        defaults = {
            'fixed': {
                'base_stake': config.get('base_stake', 10)
            },
            'martingale': {
                'base_stake': config.get('base_stake', 10),
                'loss_multiplier': config.get('loss_multiplier', 2),
                'max_stake': config.get('max_stake', 100),
                'reset_on_win': config.get('reset_on_win', True)
            },
            'anti_martingale': {
                'base_stake': config.get('base_stake', 10),
                'win_multiplier': config.get('win_multiplier', 1.5),
                'max_stake': config.get('max_stake', 100),
                'reset_on_loss': config.get('reset_on_loss', True)
            },
            'compound': {
                'base_stake': config.get('base_stake', 10),
                'profit_percentage': config.get('profit_percentage', 50),
                'max_stake': config.get('max_stake', 100)
            },
            'fibonacci': {
                'base_stake': config.get('base_stake', 10),
                'max_stake': config.get('max_stake', 100),
                'reset_on_win': config.get('reset_on_win', True)
            },
            'dalembert': {
                'base_stake': config.get('base_stake', 10),
                'increment': config.get('increment', 1),
                'max_stake': config.get('max_stake', 100)
            }
        }
        
        return defaults.get(position_sizing_type, config)
