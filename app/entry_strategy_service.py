"""
Entry Strategy Service
Evaluates entry conditions for trading systems using technical indicators
"""
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
import logging

from app.technical_indicators_service import TechnicalIndicatorsService
from app.websocket_service import DerivWebSocketService
from app.errors import ConfigurationError

logger = logging.getLogger(__name__)


class EntryStrategyService:
    """Service for evaluating entry strategy conditions"""
    
    SUPPORTED_STRATEGIES = [
        'manual',
        'rsi',
        'macd',
        'ema_cross',
        'bb',
        'sma',
        'tick_analysis',
        'price_based'
    ]
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.ws_service = DerivWebSocketService()
        self.indicators_service = TechnicalIndicatorsService()
    
    def should_enter_trade(
        self,
        entry_strategy_type: str,
        entry_conditions: Dict[str, Any],
        entry_logic: str,
        symbol: str,
        current_price: Optional[float] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate if entry conditions are met
        
        Args:
            entry_strategy_type: Type of entry strategy ('rsi', 'macd', etc.)
            entry_conditions: Configuration with rules
            entry_logic: 'all' (AND) or 'any' (OR) for multiple rules
            symbol: Trading symbol (R_100, BOOM500, etc.)
            current_price: Optional current price (if already fetched)
        
        Returns:
            Tuple of (should_enter: bool, reason: Optional[str], contract_type: Optional[str])
            contract_type: 'CALL' or 'PUT' if should enter
        """
        # Manual entry - always requires user trigger
        if entry_strategy_type == 'manual':
            return False, "Manual entry requires user trigger", None
        
        # Validate strategy type
        if entry_strategy_type not in self.SUPPORTED_STRATEGIES:
            raise ConfigurationError(f"Unsupported entry strategy: {entry_strategy_type}")
        
        # Get historical data for technical analysis
        try:
            historical_data = self._fetch_historical_data(symbol, entry_strategy_type, entry_conditions)
            
            if not historical_data or len(historical_data) < 2:
                return False, "Insufficient historical data", None
            
            # Prepare DataFrame for indicator calculations
            df = self.indicators_service.prepare_dataframe(historical_data)
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return False, f"Data fetch error: {str(e)}", None
        
        # Evaluate based on strategy type
        if entry_strategy_type == 'tick_analysis':
            return self._evaluate_tick_analysis(entry_conditions, historical_data)
        
        elif entry_strategy_type == 'price_based':
            return self._evaluate_price_based(entry_conditions, df)
        
        else:
            # Technical indicator strategies (RSI, MACD, EMA, BB, SMA)
            return self._evaluate_indicator_strategy(
                entry_strategy_type,
                entry_conditions,
                entry_logic,
                df
            )
    
    def _fetch_historical_data(
        self,
        symbol: str,
        strategy_type: str,
        conditions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical ticks or candles from Deriv API
        
        Returns:
            List of tick/candle data
        """
        # Determine how much history we need based on indicators
        count = self._calculate_required_history(strategy_type, conditions)
        
        try:
            self.ws_service.connect()
            
            # For tick analysis, get ticks
            if strategy_type == 'tick_analysis':
                request = {
                    'ticks_history': symbol,
                    'count': count,
                    'end': 'latest',
                    'style': 'ticks'
                }
            else:
                # For technical indicators, get candles (1-minute)
                request = {
                    'ticks_history': symbol,
                    'count': count,
                    'end': 'latest',
                    'style': 'candles',
                    'granularity': 60  # 1-minute candles
                }
            
            response = self.ws_service.send_and_wait(request)
            
            if 'error' in response:
                raise ConfigurationError(response['error']['message'])
            
            # Parse response
            history = response.get('history', {}) if strategy_type == 'tick_analysis' else response.get('candles', [])
            
            if strategy_type == 'tick_analysis':
                times = history.get('times', [])
                prices = history.get('prices', [])
                return [{'epoch': t, 'quote': p} for t, p in zip(times, prices)]
            else:
                return history
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise
        finally:
            self.ws_service.disconnect()
    
    def _calculate_required_history(self, strategy_type: str, conditions: Dict[str, Any]) -> int:
        """
        Calculate how many historical data points we need
        """
        if strategy_type == 'tick_analysis':
            return 10  # Last 10 ticks
        
        # For indicator-based strategies, calculate based on longest period
        rules = conditions.get('rules', [])
        max_period = 50  # Default minimum
        
        for rule in rules:
            indicator = rule.get('indicator', '')
            
            if indicator == 'rsi':
                period = rule.get('period', 14)
                max_period = max(max_period, period * 3)  # Need 3x period for RSI warmup
            
            elif indicator == 'macd':
                slow = rule.get('slow_period', 26)
                max_period = max(max_period, slow * 3)
            
            elif indicator == 'ema_cross':
                slow = rule.get('slow_period', 50)
                max_period = max(max_period, slow * 2)
            
            elif indicator in ['bb', 'sma']:
                period = rule.get('period', 20)
                max_period = max(max_period, period * 2)
        
        return min(max_period + 10, 1000)  # Cap at 1000 candles
    
    def _evaluate_tick_analysis(
        self,
        conditions: Dict[str, Any],
        ticks: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate tick-based entry conditions
        
        Examples:
        - Last digit equals/not equals specific number
        - Last tick direction (up/down)
        """
        rules = conditions.get('rules', [])
        
        if not rules or len(ticks) < 2:
            return False, "Insufficient tick data", None
        
        last_tick = ticks[-1]
        previous_tick = ticks[-2]
        
        for rule in rules:
            condition_type = rule.get('condition', '')
            
            if condition_type == 'last_digit_equals':
                last_price = last_tick['quote']
                last_digit = int(str(last_price).replace('.', '')[-1])
                target_digit = rule.get('value', 0)
                
                if last_digit == target_digit:
                    action = rule.get('action', 'buy_call')
                    contract_type = 'CALL' if 'call' in action.lower() else 'PUT'
                    return True, f"Last digit {last_digit} equals {target_digit}", contract_type
            
            elif condition_type == 'tick_direction_up':
                if last_tick['quote'] > previous_tick['quote']:
                    return True, "Tick direction is up", 'CALL'
            
            elif condition_type == 'tick_direction_down':
                if last_tick['quote'] < previous_tick['quote']:
                    return True, "Tick direction is down", 'PUT'
        
        return False, "Tick analysis conditions not met", None
    
    def _evaluate_price_based(
        self,
        conditions: Dict[str, Any],
        df
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate price-based entry conditions
        
        Examples:
        - Price above/below specific level
        - Price at support/resistance
        """
        rules = conditions.get('rules', [])
        
        if not rules or len(df) == 0:
            return False, "No price data", None
        
        current_price = float(df['close'].iloc[-1])
        
        for rule in rules:
            condition = rule.get('condition', '')
            target_price = rule.get('value', 0)
            action = rule.get('action', 'buy_call')
            
            if condition == 'price_above' and current_price > target_price:
                contract_type = 'CALL' if 'call' in action.lower() else 'PUT'
                return True, f"Price {current_price} above {target_price}", contract_type
            
            elif condition == 'price_below' and current_price < target_price:
                contract_type = 'CALL' if 'call' in action.lower() else 'PUT'
                return True, f"Price {current_price} below {target_price}", contract_type
        
        return False, "Price conditions not met", None
    
    def _evaluate_indicator_strategy(
        self,
        strategy_type: str,
        conditions: Dict[str, Any],
        entry_logic: str,
        df
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate technical indicator-based entry strategy
        
        Supports multiple indicators with AND/OR logic
        """
        rules = conditions.get('rules', [])
        
        if not rules:
            return False, "No entry rules configured", None
        
        results = []
        reasons = []
        actions = []
        
        for rule in rules:
            indicator = rule.get('indicator', '')
            condition_met = False
            reason = ""
            action = rule.get('action', 'buy_call')
            
            try:
                if indicator == 'rsi':
                    condition_met, reason = self._evaluate_rsi_rule(rule, df)
                
                elif indicator == 'macd':
                    condition_met, reason = self._evaluate_macd_rule(rule, df)
                
                elif indicator == 'ema_cross':
                    condition_met, reason = self._evaluate_ema_cross_rule(rule, df)
                
                elif indicator == 'bb':
                    condition_met, reason = self._evaluate_bb_rule(rule, df)
                
                elif indicator == 'sma':
                    condition_met, reason = self._evaluate_sma_rule(rule, df)
                
                results.append(condition_met)
                if condition_met:
                    reasons.append(reason)
                    actions.append(action)
                
            except Exception as e:
                logger.error(f"Error evaluating {indicator} rule: {e}")
                results.append(False)
        
        # Apply entry logic (all=AND, any=OR)
        if entry_logic == 'all':
            should_enter = all(results)
        else:  # 'any'
            should_enter = any(results)
        
        if should_enter and actions:
            # Use first action that triggered
            contract_type = 'CALL' if 'call' in actions[0].lower() else 'PUT'
            reason_text = '; '.join(reasons)
            return True, reason_text, contract_type
        
        return False, "Indicator conditions not met", None
    
    def _evaluate_rsi_rule(self, rule: Dict[str, Any], df) -> Tuple[bool, str]:
        """Evaluate RSI rule"""
        period = rule.get('period', 14)
        condition = rule.get('condition', 'below')
        value = rule.get('value', 30)
        
        met = self.indicators_service.evaluate_rsi_condition(df, period, condition, value)
        reason = f"RSI({period}) {condition} {value}" if met else ""
        
        return met, reason
    
    def _evaluate_macd_rule(self, rule: Dict[str, Any], df) -> Tuple[bool, str]:
        """Evaluate MACD rule"""
        fast = rule.get('fast_period', 12)
        slow = rule.get('slow_period', 26)
        signal = rule.get('signal_period', 9)
        condition = rule.get('condition', 'bullish_cross')
        
        met = self.indicators_service.evaluate_macd_condition(df, fast, slow, signal, condition)
        reason = f"MACD {condition}" if met else ""
        
        return met, reason
    
    def _evaluate_ema_cross_rule(self, rule: Dict[str, Any], df) -> Tuple[bool, str]:
        """Evaluate EMA crossover rule"""
        fast_period = rule.get('fast_period', 20)
        slow_period = rule.get('slow_period', 50)
        condition = rule.get('condition', 'fast_above_slow')
        
        met = self.indicators_service.evaluate_ema_cross_condition(df, fast_period, slow_period, condition)
        reason = f"EMA({fast_period}/{slow_period}) {condition}" if met else ""
        
        return met, reason
    
    def _evaluate_bb_rule(self, rule: Dict[str, Any], df) -> Tuple[bool, str]:
        """Evaluate Bollinger Bands rule"""
        period = rule.get('period', 20)
        std_dev = rule.get('std_dev', 2.0)
        condition = rule.get('condition', 'below_lower_band')
        
        met = self.indicators_service.evaluate_bb_condition(df, period, std_dev, condition)
        reason = f"BB({period},{std_dev}) {condition}" if met else ""
        
        return met, reason
    
    def _evaluate_sma_rule(self, rule: Dict[str, Any], df) -> Tuple[bool, str]:
        """Evaluate SMA rule"""
        period = rule.get('period', 20)
        condition = rule.get('condition', 'price_above_sma')
        
        met = self.indicators_service.evaluate_sma_condition(df, period, condition)
        reason = f"SMA({period}) {condition}" if met else ""
        
        return met, reason
    
    @staticmethod
    def validate_entry_conditions(
        entry_strategy_type: str,
        entry_conditions: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate entry conditions configuration
        
        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        if entry_strategy_type not in EntryStrategyService.SUPPORTED_STRATEGIES:
            return False, f"Unsupported entry strategy: {entry_strategy_type}"
        
        if entry_strategy_type == 'manual':
            return True, None  # Manual doesn't need conditions
        
        rules = entry_conditions.get('rules', [])
        
        if not rules:
            return False, "At least one entry rule is required"
        
        for i, rule in enumerate(rules):
            if 'indicator' not in rule:
                return False, f"Rule {i+1}: Missing 'indicator' field"
            
            if 'condition' not in rule:
                return False, f"Rule {i+1}: Missing 'condition' field"
            
            # Validate indicator-specific fields
            indicator = rule['indicator']
            
            if indicator == 'rsi':
                if 'period' not in rule or 'value' not in rule:
                    return False, f"Rule {i+1}: RSI requires 'period' and 'value'"
            
            elif indicator == 'macd':
                required = ['fast_period', 'slow_period', 'signal_period']
                if not all(field in rule for field in required):
                    return False, f"Rule {i+1}: MACD requires fast_period, slow_period, signal_period"
            
            elif indicator == 'ema_cross':
                if 'fast_period' not in rule or 'slow_period' not in rule:
                    return False, f"Rule {i+1}: EMA cross requires fast_period and slow_period"
            
            elif indicator == 'bb':
                if 'period' not in rule or 'std_dev' not in rule:
                    return False, f"Rule {i+1}: BB requires period and std_dev"
            
            elif indicator == 'sma':
                if 'period' not in rule:
                    return False, f"Rule {i+1}: SMA requires period"
        
        return True, None
