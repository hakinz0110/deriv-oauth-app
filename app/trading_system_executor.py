"""
Trading System Executor - Handles execution logic with entry strategy, position sizing, and risk management
"""
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.supabase_service import supabase
from app.trade_service import TradeService
from app.websocket_service import DerivWebSocketService
from app.entry_strategy_service import EntryStrategyService
from app.errors import DerivAPIError, ConfigurationError

logger = logging.getLogger(__name__)


class TradingSystemExecutor:
    """Executes trading systems with entry strategy evaluation, position sizing, and risk management"""
    
    def __init__(self, user_id: str, trading_system_id: str):
        self.user_id = user_id
        self.trading_system_id = trading_system_id
        self.trade_service = TradeService(user_id)
        self.ws_service = DerivWebSocketService()
        self.entry_service = EntryStrategyService(user_id)
        
        # Load trading system and user risk limits
        self.trading_system = self._load_trading_system()
        self.risk_limits = self._load_risk_limits()
        
        # Execution state for position sizing
        self.current_streak = 0
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.session_profit = Decimal('0')
        self.session_trades = 0
        
    def _load_trading_system(self) -> Dict[str, Any]:
        """Load trading system configuration from database"""
        result = supabase.table('trading_systems').select('*').eq('id', self.trading_system_id).eq('user_id', self.user_id).single().execute()
        
        if not result.data:
            raise ConfigurationError(f"Trading system {self.trading_system_id} not found")
        
        if not result.data['is_active']:
            raise ConfigurationError(f"Trading system {self.trading_system_id} is not active")
        
        return result.data
    
    def _load_risk_limits(self) -> Dict[str, Any]:
        """Load user risk limits from preferences"""
        result = supabase.table('user_preferences').select('*').eq('user_id', self.user_id).single().execute()
        
        if not result.data or not result.data.get('preferences'):
            return self._get_default_risk_limits()
        
        prefs = result.data['preferences']
        return {
            'max_daily_loss': Decimal(str(prefs.get('max_daily_loss', 100))),
            'max_trade_size': Decimal(str(prefs.get('max_trade_size', 50))),
            'max_concurrent_trades': int(prefs.get('max_concurrent_trades', 3)),
            'daily_profit_target': Decimal(str(prefs.get('daily_profit_target', 500))),
            'max_stake_percentage': Decimal(str(prefs.get('max_stake_percentage', 5))),
            'stop_on_profit_target': prefs.get('stop_on_profit_target', False),
            'stop_on_loss_limit': prefs.get('stop_on_loss_limit', True)
        }
    
    def _get_default_risk_limits(self) -> Dict[str, Any]:
        """Default risk limits if none configured"""
        return {
            'max_daily_loss': Decimal('100'),
            'max_trade_size': Decimal('50'),
            'max_concurrent_trades': 3,
            'daily_profit_target': Decimal('500'),
            'max_stake_percentage': Decimal('5'),
            'stop_on_profit_target': False,
            'stop_on_loss_limit': True
        }
    
    def check_risk_limits(self) -> Tuple[bool, Optional[str]]:
        """
        Check if risk limits allow trading
        Returns: (can_trade: bool, reason: Optional[str])
        """
        # Check daily loss limit
        if self.risk_limits['stop_on_loss_limit']:
            daily_loss = self._get_daily_profit_loss()
            if daily_loss <= -self.risk_limits['max_daily_loss']:
                return False, f"Daily loss limit reached ({daily_loss})"
        
        # Check profit target
        if self.risk_limits['stop_on_profit_target']:
            daily_profit = self._get_daily_profit_loss()
            if daily_profit >= self.risk_limits['daily_profit_target']:
                return False, f"Daily profit target reached ({daily_profit})"
        
        # Check concurrent trades
        open_positions = self.trade_service.get_portfolio()
        if len(open_positions) >= self.risk_limits['max_concurrent_trades']:
            return False, f"Maximum concurrent trades reached ({self.risk_limits['max_concurrent_trades']})"
        
        return True, None
    
    def _get_daily_profit_loss(self) -> Decimal:
        """Calculate today's profit/loss from profit table"""
        try:
            today = datetime.utcnow().date()
            start_timestamp = int(datetime.combine(today, datetime.min.time()).timestamp())
            
            profit_table = self.trade_service.get_profit_table(
                date_from=start_timestamp,
                limit=1000
            )
            
            total = Decimal('0')
            for trade in profit_table.get('transactions', []):
                total += Decimal(str(trade.get('sell_price', 0))) - Decimal(str(trade.get('buy_price', 0)))
            
            return total
        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}")
            return Decimal('0')
    
    def should_enter_trade(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate if trading system should enter trade based on entry strategy
        Returns: (should_enter: bool, reason: Optional[str], contract_type: Optional[str])
        """
        # Check risk limits first
        can_trade, reason = self.check_risk_limits()
        if not can_trade:
            return False, reason, None
        
        # Evaluate entry strategy
        entry_strategy_type = self.trading_system['entry_strategy_type']
        entry_conditions = self.trading_system['entry_conditions']
        entry_logic = self.trading_system['entry_logic']
        symbol = self.trading_system['symbol']
        
        try:
            should_enter, entry_reason, contract_type = self.entry_service.should_enter_trade(
                entry_strategy_type,
                entry_conditions,
                entry_logic,
                symbol
            )
            
            return should_enter, entry_reason, contract_type
            
        except Exception as e:
            logger.error(f"Error evaluating entry strategy: {e}")
            return False, f"Entry evaluation error: {str(e)}", None
    
    def calculate_stake(self) -> Decimal:
        """
        Calculate stake amount based on position sizing type and current state
        """
        config = self.trading_system['position_sizing_config']
        base_stake = Decimal(str(config.get('base_stake', 10)))
        position_sizing_type = self.trading_system['position_sizing_type']
        
        if position_sizing_type == 'fixed':
            stake = base_stake
        
        elif position_sizing_type == 'martingale':
            if self.consecutive_losses > 0:
                multiplier = Decimal(str(config.get('loss_multiplier', 2)))
                stake = base_stake * (multiplier ** self.consecutive_losses)
            else:
                stake = base_stake
        
        elif position_sizing_type == 'anti_martingale':
            if self.consecutive_wins > 0:
                multiplier = Decimal(str(config.get('win_multiplier', 1.5)))
                stake = base_stake * (multiplier ** self.consecutive_wins)
            else:
                stake = base_stake
        
        elif position_sizing_type == 'compound':
            profit_percentage = Decimal(str(config.get('profit_percentage', 50))) / 100
            stake = base_stake + (self.session_profit * profit_percentage)
            stake = max(stake, base_stake)  # Never go below base
        
        elif position_sizing_type == 'fibonacci':
            fib_sequence = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
            index = min(self.consecutive_losses, len(fib_sequence) - 1)
            stake = base_stake * Decimal(fib_sequence[index])
        
        elif position_sizing_type == 'dalembert':
            increment = Decimal(str(config.get('increment', 1)))
            if self.consecutive_losses > 0:
                stake = base_stake + (increment * self.consecutive_losses)
            else:
                stake = max(base_stake - increment, base_stake)
        
        else:
            stake = base_stake
        
        # Apply limits
        max_stake = Decimal(str(config.get('max_stake', 100)))
        stake = min(stake, max_stake)
        stake = min(stake, self.risk_limits['max_trade_size'])
        
        # Round to 2 decimal places
        return stake.quantize(Decimal('0.01'))
    
    def execute_trade(self) -> Dict[str, Any]:
        """
        Execute a trade based on trading system configuration
        Evaluates entry strategy, calculates stake, and executes trade
        """
        # Check if should enter trade
        should_enter, reason, contract_type = self.should_enter_trade()
        
        if not should_enter:
            logger.info(f"Trading system {self.trading_system_id} skipping trade: {reason}")
            return {
                'success': False,
                'reason': reason,
                'action': 'skip'
            }
        
        # Calculate stake using position sizing
        stake = self.calculate_stake()
        
        # Get proposal
        try:
            proposal = self.trade_service.get_proposal({
                'contract_type': contract_type,
                'symbol': self.trading_system['symbol'],
                'amount': float(stake),
                'duration': self.trading_system['duration'],
                'duration_unit': self.trading_system['duration_unit'],
                'basis': 'stake'
            })
            
            # Execute buy
            contract = self.trade_service.buy_contract(proposal['id'])
            
            # Update execution state
            self.session_trades += 1
            
            # Record trade in database
            self._record_trade(contract, stake)
            
            # Update trading system stats
            self._update_trading_system_stats()
            
            logger.info(f"Trading system {self.trading_system_id} executed trade: {contract['contract_id']}")
            
            return {
                'success': True,
                'contract_id': contract['contract_id'],
                'contract_type': contract_type,
                'stake': float(stake),
                'buy_price': contract['buy_price'],
                'action': 'buy',
                'entry_reason': reason
            }
            
        except DerivAPIError as e:
            logger.error(f"Trade execution failed: {e}")
            return {
                'success': False,
                'reason': str(e),
                'action': 'error'
            }
    
    def _record_trade(self, contract: Dict[str, Any], stake: Decimal):
        """Record trade execution in database"""
        try:
            supabase.table('trades').insert({
                'user_id': self.user_id,
                'trading_system_id': self.trading_system_id,
                'contract_id': contract['contract_id'],
                'contract_type': contract.get('contract_type', self.trading_system['contract_type']),
                'symbol': self.trading_system['symbol'],
                'stake': float(stake),
                'buy_price': contract['buy_price'],
                'entry_time': datetime.utcnow().isoformat(),
                'status': 'open'
            }).execute()
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
    
    def _update_trading_system_stats(self):
        """Update trading system last_used_at timestamp"""
        try:
            supabase.table('trading_systems')\
                .update({'last_used_at': datetime.utcnow().isoformat()})\
                .eq('id', self.trading_system_id)\
                .execute()
        except Exception as e:
            logger.error(f"Failed to update trading system stats: {e}")
    
    def update_trade_result(self, contract_id: str, result: Dict[str, Any]):
        """
        Update trading system state after trade closes
        """
        profit = Decimal(str(result.get('profit', 0)))
        is_win = profit > 0
        
        # Update streaks for position sizing
        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        
        # Update session profit
        self.session_profit += profit
        
        # Check reset conditions
        config = self.trading_system['position_sizing_config']
        position_sizing_type = self.trading_system['position_sizing_type']
        
        if position_sizing_type in ['martingale', 'fibonacci', 'dalembert']:
            reset_on_win = config.get('reset_on_win', True)
            if is_win and reset_on_win:
                self.consecutive_losses = 0
        
        elif position_sizing_type == 'anti_martingale':
            reset_on_loss = config.get('reset_on_loss', True)
            if not is_win and reset_on_loss:
                self.consecutive_wins = 0
        
        # Update trade record
        try:
            supabase.table('trades')\
                .update({
                    'exit_time': datetime.utcnow().isoformat(),
                    'sell_price': result.get('sell_price'),
                    'profit': float(profit),
                    'status': 'closed'
                })\
                .eq('contract_id', contract_id)\
                .execute()
        except Exception as e:
            logger.error(f"Failed to update trade result: {e}")
        
        logger.info(f"Trading system {self.trading_system_id} trade closed: {contract_id}, profit: {profit}")


class TradingSystemBacktestEngine:
    """Backtest trading systems using historical data from Deriv API"""
    
    def __init__(self, user_id: str, trading_system_id: str):
        self.user_id = user_id
        self.trading_system_id = trading_system_id
        self.trade_service = TradeService(user_id)
        self.ws_service = DerivWebSocketService()
    
    def run_backtest(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: Decimal
    ) -> Dict[str, Any]:
        """
        Run backtest using historical ticks data
        """
        logger.info(f"Starting backtest for trading system {self.trading_system_id}")
        
        # Fetch historical ticks
        ticks = self._fetch_historical_ticks(symbol, start_date, end_date)
        
        if not ticks:
            raise ConfigurationError("No historical data available for backtest period")
        
        # Initialize backtest state
        balance = initial_balance
        trades = []
        equity_curve = []
        
        # Create executor
        executor = TradingSystemExecutor(self.user_id, self.trading_system_id)
        
        # Simulate trades
        for i, tick in enumerate(ticks):
            # Check if entry conditions are met
            should_enter, entry_reason, contract_type = executor.should_enter_trade()
            
            if should_enter:
                stake = executor.calculate_stake()
                
                # Simulate trade outcome (simplified)
                outcome = self._simulate_trade_outcome(tick, contract_type, stake, ticks[i:i+100])
                
                balance += outcome['profit']
                trades.append(outcome)
                executor.update_trade_result(outcome['contract_id'], outcome)
            
            # Record equity
            equity_curve.append({
                'timestamp': tick['epoch'],
                'balance': float(balance)
            })
        
        # Calculate statistics
        stats = self._calculate_backtest_stats(trades, initial_balance, balance)
        
        # Save backtest results
        backtest_id = self._save_backtest_results(
            symbol, start_date, end_date, initial_balance, balance, trades, stats
        )
        
        return {
            'backtest_id': backtest_id,
            'initial_balance': float(initial_balance),
            'final_balance': float(balance),
            'total_trades': len(trades),
            'statistics': stats,
            'equity_curve': equity_curve
        }
    
    def _fetch_historical_ticks(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical ticks from Deriv API"""
        try:
            self.ws_service.connect(self.trade_service.token_data['token'])
            
            start_epoch = int(start_date.timestamp())
            end_epoch = int(end_date.timestamp())
            
            request = {
                'ticks_history': symbol,
                'start': start_epoch,
                'end': end_epoch,
                'style': 'ticks',
                'count': 5000
            }
            
            response = self.ws_service.send_and_wait(request)
            
            if 'error' in response:
                raise DerivAPIError(response['error']['message'])
            
            history = response.get('history', {})
            times = history.get('times', [])
            prices = history.get('prices', [])
            
            ticks = []
            for epoch, price in zip(times, prices):
                ticks.append({
                    'epoch': epoch,
                    'quote': price,
                    'symbol': symbol
                })
            
            return ticks
            
        except Exception as e:
            logger.error(f"Failed to fetch historical ticks: {e}")
            return []
        finally:
            self.ws_service.disconnect()
    
    def _simulate_trade_outcome(
        self,
        entry_tick: Dict[str, Any],
        contract_type: str,
        stake: Decimal,
        future_ticks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simulate trade outcome using future ticks"""
        import uuid
        
        entry_price = entry_tick['quote']
        duration = 5  # Simplified for backtest
        
        if len(future_ticks) >= duration:
            exit_tick = future_ticks[duration - 1]
            exit_price = exit_tick['quote']
        else:
            return {
                'contract_id': str(uuid.uuid4()),
                'profit': Decimal('0'),
                'sell_price': float(stake),
                'status': 'incomplete'
            }
        
        # Determine win/loss
        if contract_type == 'CALL':
            is_win = exit_price > entry_price
        else:  # PUT
            is_win = exit_price < entry_price
        
        # Calculate payout (simplified - using 1.9x payout ratio)
        payout_ratio = Decimal('1.9')
        if is_win:
            payout = stake * payout_ratio
            profit = payout - stake
        else:
            payout = Decimal('0')
            profit = -stake
        
        return {
            'contract_id': str(uuid.uuid4()),
            'profit': profit,
            'sell_price': float(payout),
            'buy_price': float(stake),
            'entry_price': entry_price,
            'exit_price': exit_price,
            'is_win': is_win,
            'status': 'closed'
        }
    
    def _calculate_backtest_stats(
        self,
        trades: List[Dict[str, Any]],
        initial_balance: Decimal,
        final_balance: Decimal
    ) -> Dict[str, Any]:
        """Calculate backtest statistics"""
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0
            }
        
        winning_trades = [t for t in trades if t['profit'] > 0]
        losing_trades = [t for t in trades if t['profit'] <= 0]
        
        total_profit = final_balance - initial_balance
        win_rate = (len(winning_trades) / len(trades)) * 100 if trades else 0
        
        # Calculate max drawdown
        peak = initial_balance
        max_drawdown = Decimal('0')
        running_balance = initial_balance
        
        for trade in trades:
            running_balance += trade['profit']
            if running_balance > peak:
                peak = running_balance
            drawdown = ((peak - running_balance) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # Calculate Sharpe ratio (simplified)
        if trades:
            returns = [float(t['profit']) / float(initial_balance) for t in trades]
            avg_return = sum(returns) / len(returns)
            std_dev = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_dev) if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(float(win_rate), 2),
            'total_profit': float(total_profit),
            'max_drawdown': float(max_drawdown),
            'sharpe_ratio': round(sharpe_ratio, 2)
        }
    
    def _save_backtest_results(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_balance: Decimal,
        final_balance: Decimal,
        trades: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> str:
        """Save backtest results to database"""
        result = supabase.table('trading_system_backtests').insert({
            'trading_system_id': self.trading_system_id,
            'user_id': self.user_id,
            'symbol': symbol,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'initial_balance': float(initial_balance),
            'final_balance': float(final_balance),
            'total_trades': stats['total_trades'],
            'winning_trades': stats['winning_trades'],
            'losing_trades': stats['losing_trades'],
            'win_rate': stats['win_rate'],
            'total_profit': stats['total_profit'],
            'max_drawdown': stats['max_drawdown'],
            'sharpe_ratio': stats['sharpe_ratio'],
            'trades_data': trades
        }).execute()
        
        return result.data[0]['id']
