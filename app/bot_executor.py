"""
Bot Executor - Main Trading Loop for Automated Bot
===================================================
Handles the bot execution thread, market monitoring, signal generation,
and trade execution across multiple trading systems.
"""

import threading
import time
import json
import websocket
from datetime import datetime, timezone
from decimal import Decimal
from app.bot_service import BotService, BotServiceError
from app.trading_system_service import TradingSystemService
from app.trading_system_executor import TradingSystemExecutor
from app.entry_strategy_service import EntryStrategyService
from app.technical_indicators_service import TechnicalIndicatorsService
from app.websocket_service import WebSocketService
from app.session_service import SessionService
from app.trade_service import TradeService
from flask import current_app


class BotExecutor:
    """
    Main bot executor with WebSocket-based market monitoring.
    Runs in a separate thread and manages multiple trading systems.
    """
    
    # Global registry of running bot threads
    _active_bots = {}
    _lock = threading.Lock()
    
    def __init__(self, bot_id, user_id, access_token, account_id):
        """
        Initialize bot executor.
        
        Args:
            bot_id: Bot UUID
            user_id: User identifier
            access_token: Deriv OAuth access token
            account_id: Selected trading account ID
        """
        self.bot_id = bot_id
        self.user_id = user_id
        self.access_token = access_token
        self.account_id = account_id
        
        # Thread control
        self.thread = None
        self.stop_requested = False
        self.is_running = False
        
        # WebSocket connection
        self.ws = None
        self.ws_url = None
        self.ws_connected = False
        self.last_heartbeat = None
        
        # Market data
        self.market_data = {}  # symbol -> {price, history}
        self.subscribed_symbols = set()
        
        # Position tracking
        self.open_positions = {}  # contract_id -> position_data
        self.contract_subscriptions = {}  # contract_id -> subscription_id
        
        # Configuration
        self.check_interval = 5  # seconds
        self.max_concurrent_trades = 3
        self.heartbeat_interval = 30  # seconds
        
        # Statistics
        self.start_time = None
        self.last_check_time = None
        self.trades_executed = 0
    
    @classmethod
    def start_bot(cls, bot_id, user_id, access_token, account_id):
        """
        Start bot in background thread.
        
        Args:
            bot_id: Bot UUID
            user_id: User identifier
            access_token: Deriv OAuth access token
            account_id: Selected trading account ID
            
        Returns:
            BotExecutor: Bot executor instance
            
        Raises:
            BotServiceError: If bot is already running
        """
        with cls._lock:
            # Check if bot already running
            if bot_id in cls._active_bots:
                raise BotServiceError('Bot is already running', 'BOT_ALREADY_RUNNING')
            
            # Create executor instance
            executor = cls(bot_id, user_id, access_token, account_id)
            
            # Start thread
            executor.thread = threading.Thread(
                target=executor._run_loop,
                name=f'Bot-{bot_id[:8]}',
                daemon=True
            )
            executor.thread.start()
            
            # Register in active bots
            cls._active_bots[bot_id] = executor
            
            BotService.log_event(
                bot_id=bot_id,
                user_id=user_id,
                log_level='info',
                message='Bot started successfully',
                event_type='bot_start'
            )
            
            # Create notification
            from app.notification_service import NotificationService
            from app.bot_service import BotService as BS
            bot_data = BS.get_bot_by_id(bot_id, user_id)
            if bot_data:
                NotificationService.notify_bot_started(user_id, bot_data)
            
            return executor
    
    @classmethod
    def stop_bot(cls, bot_id):
        """
        Stop running bot gracefully.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            bool: True if stopped successfully
        """
        with cls._lock:
            executor = cls._active_bots.get(bot_id)
            
            if not executor:
                return False
            
            # Request stop
            executor.stop_requested = True
            
            # Wait for thread to finish (max 10 seconds)
            if executor.thread and executor.thread.is_alive():
                executor.thread.join(timeout=10)
            
            # Close WebSocket
            if executor.ws:
                try:
                    executor.ws.close()
                except:
                    pass
            
            # Remove from active bots
            del cls._active_bots[bot_id]
            
            BotService.log_event(
                bot_id=bot_id,
                user_id=executor.user_id,
                log_level='info',
                message='Bot stopped successfully',
                event_type='bot_stop'
            )
            
            # Create notification
            from app.notification_service import NotificationService
            from app.bot_service import BotService as BS
            bot_data = BS.get_bot_by_id(bot_id, executor.user_id)
            if bot_data:
                NotificationService.notify_bot_stopped(executor.user_id, bot_data)
            
            return True
    
    @classmethod
    def get_bot_executor(cls, bot_id):
        """
        Get running bot executor instance.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            BotExecutor or None
        """
        return cls._active_bots.get(bot_id)
    
    @classmethod
    def is_bot_running(cls, bot_id):
        """
        Check if bot is currently running.
        
        Args:
            bot_id: Bot UUID
            
        Returns:
            bool
        """
        return bot_id in cls._active_bots
    
    def _run_loop(self):
        """Main bot execution loop."""
        self.is_running = True
        self.start_time = datetime.now(timezone.utc)
        
        try:
            # Update bot status
            BotService.update_bot_status(self.bot_id, 'starting')
            
            # Get bot configuration
            bot = BotService.get_bot_by_id(self.bot_id, self.user_id)
            if not bot:
                raise BotServiceError('Bot not found', 'BOT_NOT_FOUND')
            
            config = bot.get('config', {})
            self.check_interval = config.get('check_interval_seconds', 5)
            self.max_concurrent_trades = config.get('max_concurrent_trades', 3)
            
            # Get active trading systems
            active_system_ids = bot.get('active_trading_systems', [])
            
            if not active_system_ids:
                raise BotServiceError('No active trading systems configured', 'NO_TRADING_SYSTEMS')
            
            # Connect WebSocket
            self._connect_websocket()
            
            # Subscribe to symbols from all trading systems
            self._subscribe_to_trading_systems(active_system_ids)
            
            # Update status to running
            BotService.update_bot_status(self.bot_id, 'running')
            
            # Main loop
            last_heartbeat_check = time.time()
            
            while not self.stop_requested:
                current_time = time.time()
                
                # Check heartbeat
                if current_time - last_heartbeat_check >= self.heartbeat_interval:
                    self._send_heartbeat()
                    last_heartbeat_check = current_time
                
                # Process trading systems
                self._process_trading_systems(active_system_ids)
                
                # Monitor open positions for closure
                self._monitor_open_positions()
                
                # Update last check time
                self.last_check_time = datetime.now(timezone.utc)
                BotService.update_current_positions(
                    self.bot_id,
                    list(self.open_positions.values())
                )
                
                # Sleep
                time.sleep(self.check_interval)
        
        except Exception as e:
            error_msg = f'Bot error: {str(e)}'
            
            BotService.update_bot_status(self.bot_id, 'error', error_msg)
            BotService.add_error_to_log(
                self.bot_id,
                error_msg,
                {'exception': str(type(e).__name__)}
            )
            
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='error',
                message=error_msg,
                event_type='bot_error',
                context_data={'exception_type': str(type(e).__name__)}
            )
            
            # Create error notification
            from app.notification_service import NotificationService
            from app.bot_service import BotService as BS
            bot_data = BS.get_bot_by_id(self.bot_id, self.user_id)
            if bot_data:
                NotificationService.notify_bot_error(self.user_id, bot_data, str(e))
        
        finally:
            # Cleanup
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
            
            BotService.update_bot_status(self.bot_id, 'inactive')
            BotService.update_websocket_status(self.bot_id, False)
            
            self.is_running = False
    
    def _connect_websocket(self):
        """Connect to Deriv WebSocket with authentication."""
        try:
            # Request authenticated WebSocket URL
            self.ws_url = WebSocketService.request_websocket_url(
                self.account_id,
                self.access_token
            )
            
            # Create WebSocket connection
            self.ws = websocket.create_connection(
                self.ws_url,
                timeout=10
            )
            
            self.ws_connected = True
            self.last_heartbeat = datetime.now(timezone.utc)
            
            BotService.update_websocket_status(self.bot_id, True)
            
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='info',
                message='WebSocket connected successfully',
                event_type='websocket_connected'
            )
            
        except Exception as e:
            raise BotServiceError(
                f'Failed to connect WebSocket: {str(e)}',
                'WEBSOCKET_CONNECTION_FAILED'
            )
    
    def _send_heartbeat(self):
        """Send ping/pong heartbeat to keep connection alive."""
        if not self.ws or not self.ws_connected:
            return
        
        try:
            # Send ping
            ping_msg = json.dumps({'ping': 1})
            self.ws.send(ping_msg)
            
            # Wait for pong (with timeout)
            self.ws.settimeout(5)
            response = self.ws.recv()
            
            if response:
                self.last_heartbeat = datetime.now(timezone.utc)
                BotService.update_websocket_status(
                    self.bot_id,
                    True,
                    self.last_heartbeat.isoformat()
                )
        
        except Exception as e:
            # Connection lost
            self.ws_connected = False
            BotService.update_websocket_status(self.bot_id, False)
            
            # Attempt reconnection
            try:
                self._connect_websocket()
                self._resubscribe_symbols()
            except:
                raise BotServiceError(
                    'WebSocket connection lost and reconnection failed',
                    'WEBSOCKET_RECONNECTION_FAILED'
                )
    
    def _subscribe_to_trading_systems(self, system_ids):
        """
        Subscribe to market data for all trading systems.
        
        Args:
            system_ids: List of trading system UUIDs
        """
        for system_id in system_ids:
            try:
                # Get trading system
                service = TradingSystemService(self.user_id)
                system = service.get_trading_system(system_id)
                
                if not system or not system.get('is_active'):
                    continue
                
                symbol = system.get('symbol')
                
                if symbol and symbol not in self.subscribed_symbols:
                    self._subscribe_to_symbol(symbol)
                    self.subscribed_symbols.add(symbol)
            
            except Exception as e:
                BotService.log_event(
                    bot_id=self.bot_id,
                    user_id=self.user_id,
                    log_level='warning',
                    message=f'Failed to subscribe to system {system_id}: {str(e)}',
                    event_type='subscription_error',
                    trading_system_id=system_id
                )
    
    def _subscribe_to_symbol(self, symbol):
        """
        Subscribe to tick stream for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'R_100')
        """
        if not self.ws or not self.ws_connected:
            return
        
        try:
            subscribe_msg = json.dumps({
                'ticks': symbol,
                'subscribe': 1
            })
            
            self.ws.send(subscribe_msg)
            
            # Initialize market data
            self.market_data[symbol] = {
                'price': None,
                'history': [],
                'last_update': None
            }
            
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='debug',
                message=f'Subscribed to {symbol}',
                event_type='symbol_subscribed',
                context_data={'symbol': symbol}
            )
        
        except Exception as e:
            raise BotServiceError(
                f'Failed to subscribe to {symbol}: {str(e)}',
                'SYMBOL_SUBSCRIPTION_FAILED'
            )
    
    def _resubscribe_symbols(self):
        """Resubscribe to all symbols after reconnection."""
        for symbol in list(self.subscribed_symbols):
            self._subscribe_to_symbol(symbol)
    
    def _process_trading_systems(self, system_ids):
        """
        Process each trading system for signals and execution.
        
        Args:
            system_ids: List of trading system UUIDs
        """
        # Check if we can take more positions
        if len(self.open_positions) >= self.max_concurrent_trades:
            return
        
        for system_id in system_ids:
            try:
                self._process_single_system(system_id)
            
            except Exception as e:
                BotService.log_event(
                    bot_id=self.bot_id,
                    user_id=self.user_id,
                    log_level='error',
                    message=f'Error processing system {system_id}: {str(e)}',
                    event_type='system_processing_error',
                    trading_system_id=system_id
                )
    
    def _process_single_system(self, system_id):
        """
        Process a single trading system.
        
        Args:
            system_id: Trading system UUID
        """
        # Get trading system
        service = TradingSystemService(self.user_id)
        system = service.get_trading_system(system_id)
        
        if not system or not system.get('is_active'):
            return
        
        symbol = system.get('symbol')
        
        # Check if we have market data
        if symbol not in self.market_data or not self.market_data[symbol]['price']:
            return
        
        # Get current market data
        market_data = self.market_data[symbol]
        
        # Check entry signal
        entry_signal = self._check_entry_signal(system, market_data)
        
        if entry_signal:
            # Execute trade
            self._execute_trade(system, market_data)
    
    def _check_entry_signal(self, system, market_data):
        """
        Check if trading system generates entry signal.
        
        Args:
            system: Trading system dict
            market_data: Current market data
            
        Returns:
            bool: True if signal detected
        """
        entry_type = system.get('entry_strategy_type')
        
        # Manual entry - no automatic signals
        if entry_type == 'manual':
            return False
        
        try:
            # Use entry strategy service
            signal = EntryStrategyService.evaluate_entry(
                entry_type=entry_type,
                entry_conditions=system.get('entry_conditions', {}),
                entry_logic=system.get('entry_logic', 'AND'),
                symbol=system.get('symbol'),
                current_price=market_data['price'],
                price_history=market_data['history']
            )
            
            if signal:
                BotService.log_event(
                    bot_id=self.bot_id,
                    user_id=self.user_id,
                    log_level='info',
                    message=f'Entry signal detected for {system.get("name")}',
                    event_type='signal_detected',
                    trading_system_id=system['id'],
                    context_data={
                        'entry_type': entry_type,
                        'symbol': system.get('symbol'),
                        'price': str(market_data['price'])
                    }
                )
            
            return signal
        
        except Exception as e:
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='error',
                message=f'Signal evaluation error: {str(e)}',
                event_type='signal_error',
                trading_system_id=system['id']
            )
            return False
    
    def _execute_trade(self, system, market_data):
        """
        Execute trade for trading system.
        
        Args:
            system: Trading system dict
            market_data: Current market data
        """
        try:
            # Use trading system executor
            executor = TradingSystemExecutor(self.user_id, system['id'])
            
            # Execute trade
            result = executor.execute_trade(market_data)
            
            if result and result.get('status') == 'success':
                # Track position
                contract_id = result.get('contract_id')
                
                if contract_id:
                    self.open_positions[contract_id] = {
                        'contract_id': contract_id,
                        'trading_system_id': system['id'],
                        'symbol': system.get('symbol'),
                        'opened_at': datetime.now(timezone.utc).isoformat(),
                        'stake': result.get('stake'),
                        'contract_type': system.get('contract_type')
                    }
                    
                    self.trades_executed += 1
                    
                    # Subscribe to contract monitoring immediately
                    self._subscribe_to_contract(contract_id)
                
                BotService.log_event(
                    bot_id=self.bot_id,
                    user_id=self.user_id,
                    log_level='info',
                    message=f'Trade executed: {system.get("name")}',
                    event_type='trade_opened',
                    trading_system_id=system['id'],
                    trade_id=contract_id,
                    context_data=result
                )
        
        except Exception as e:
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='error',
                message=f'Trade execution failed: {str(e)}',
                event_type='trade_error',
                trading_system_id=system['id']
            )
    
    def _monitor_open_positions(self):
        """
        Monitor all open positions for closure using proposal_open_contract.
        When a position closes, update the database and dispatch event.
        """
        if not self.ws or not self.ws_connected:
            return
        
        for contract_id in list(self.open_positions.keys()):
            try:
                # Subscribe to contract if not already subscribed
                if contract_id not in self.contract_subscriptions:
                    self._subscribe_to_contract(contract_id)
                
                # Check for updates by receiving messages
                self.ws.settimeout(0.1)  # Non-blocking check
                try:
                    message = self.ws.recv()
                    if message:
                        data = json.loads(message)
                        self._handle_contract_update(data)
                except websocket.WebSocketTimeoutException:
                    pass  # No message available, continue
                
            except Exception as e:
                BotService.log_event(
                    bot_id=self.bot_id,
                    user_id=self.user_id,
                    log_level='warning',
                    message=f'Error monitoring contract {contract_id}: {str(e)}',
                    event_type='monitoring_error',
                    context_data={'contract_id': contract_id}
                )
    
    def _subscribe_to_contract(self, contract_id):
        """
        Subscribe to proposal_open_contract for real-time position monitoring.
        
        Args:
            contract_id: Contract ID to monitor
        """
        if not self.ws or not self.ws_connected:
            return
        
        try:
            subscribe_msg = json.dumps({
                'proposal_open_contract': 1,
                'contract_id': contract_id,
                'subscribe': 1
            })
            
            self.ws.send(subscribe_msg)
            
            # Mark as subscribed (will get subscription_id in response)
            self.contract_subscriptions[contract_id] = 'pending'
            
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='debug',
                message=f'Subscribed to contract {contract_id} monitoring',
                event_type='contract_subscribed',
                context_data={'contract_id': contract_id}
            )
        
        except Exception as e:
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='error',
                message=f'Failed to subscribe to contract {contract_id}: {str(e)}',
                event_type='contract_subscription_error',
                context_data={'contract_id': contract_id}
            )
    
    def _handle_contract_update(self, data):
        """
        Handle contract update from proposal_open_contract subscription.
        
        Args:
            data: WebSocket message data
        """
        # Handle subscription confirmation
        if 'subscription' in data:
            subscription = data['subscription']
            subscription_id = subscription.get('id')
            
            # Link subscription_id to contract_id if this is contract subscription
            # (We'll identify by matching with pending subscriptions)
            for contract_id, sub_id in self.contract_subscriptions.items():
                if sub_id == 'pending':
                    self.contract_subscriptions[contract_id] = subscription_id
                    break
        
        # Handle contract updates
        if 'proposal_open_contract' in data:
            contract_data = data['proposal_open_contract']
            contract_id = contract_data.get('contract_id')
            
            if not contract_id or contract_id not in self.open_positions:
                return
            
            # Check if contract is closed
            is_sold = contract_data.get('is_sold', 0) == 1
            status = contract_data.get('status')
            
            if is_sold or status in ['sold', 'won', 'lost']:
                self._handle_trade_closure(contract_id, contract_data)
    
    def _handle_trade_closure(self, contract_id, contract_data):
        """
        Handle trade closure - update database and notify frontend.
        
        Args:
            contract_id: Contract ID that closed
            contract_data: Contract data from Deriv API
        """
        try:
            position = self.open_positions.get(contract_id)
            if not position:
                return
            
            # Extract P&L and outcome from contract_data
            buy_price = float(contract_data.get('buy_price', 0))
            sell_price = float(contract_data.get('sell_price', 0))
            pnl = sell_price - buy_price
            pnl_percentage = (pnl / buy_price * 100) if buy_price > 0 else 0
            
            profit = contract_data.get('profit', pnl)
            outcome = 'win' if profit > 0 else 'loss' if profit < 0 else 'breakeven'
            
            # Update trade in database
            from app.supabase_service import SupabaseService
            
            trade_update = {
                'exit_price': sell_price,
                'pnl': pnl,
                'pnl_percentage': pnl_percentage,
                'outcome': outcome,
                'closed_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Find and update the trade by deriv_contract_id
            supabase = SupabaseService.get_client()
            result = supabase.table('trades').update(trade_update).eq(
                'deriv_contract_id', str(contract_id)
            ).eq('user_id', self.user_id).execute()
            
            # Remove from open positions
            del self.open_positions[contract_id]
            
            # Unsubscribe from contract
            if contract_id in self.contract_subscriptions:
                subscription_id = self.contract_subscriptions[contract_id]
                if subscription_id and subscription_id != 'pending':
                    forget_msg = json.dumps({'forget': subscription_id})
                    self.ws.send(forget_msg)
                del self.contract_subscriptions[contract_id]
            
            # Log closure
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='info',
                message=f'Trade closed: {outcome} {pnl:+.2f}',
                event_type='trade_closed',
                trade_id=contract_id,
                trading_system_id=position.get('trading_system_id'),
                context_data={
                    'contract_id': contract_id,
                    'outcome': outcome,
                    'pnl': float(pnl),
                    'pnl_percentage': float(pnl_percentage),
                    'buy_price': buy_price,
                    'sell_price': sell_price
                }
            )
            
            # Create notification for user
            from app.notification_service import NotificationService
            NotificationService.notify_trade_closed(
                user_id=self.user_id,
                trade_data={
                    'contract_id': contract_id,
                    'symbol': position.get('symbol'),
                    'outcome': outcome,
                    'pnl': pnl
                }
            )
            
            # Dispatch frontend event (will be handled by JavaScript)
            # This is logged so frontend polling can detect it
            current_app.logger.info(f'TRADE_COMPLETED: {contract_id}|{outcome}|{pnl}')
        
        except Exception as e:
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='error',
                message=f'Error handling trade closure: {str(e)}',
                event_type='closure_error',
                context_data={'contract_id': contract_id}
            )
    
    def pause(self):
        """Pause bot (stop trading but maintain connection)."""
        if self.bot_id in BotExecutor._active_bots:
            BotService.update_bot_status(self.bot_id, 'paused')
            
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='info',
                message='Bot paused',
                event_type='bot_paused'
            )
    
    def resume(self):
        """Resume bot from paused state."""
        if self.bot_id in BotExecutor._active_bots:
            BotService.update_bot_status(self.bot_id, 'running')
            BotService.clear_error_state(self.bot_id)
            
            BotService.log_event(
                bot_id=self.bot_id,
                user_id=self.user_id,
                log_level='info',
                message='Bot resumed',
                event_type='bot_resumed'
            )
    
    def get_status(self):
        """
        Get current bot status.
        
        Returns:
            dict: Bot status information
        """
        return {
            'bot_id': self.bot_id,
            'is_running': self.is_running,
            'ws_connected': self.ws_connected,
            'subscribed_symbols': list(self.subscribed_symbols),
            'open_positions_count': len(self.open_positions),
            'trades_executed': self.trades_executed,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'uptime_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
        }
