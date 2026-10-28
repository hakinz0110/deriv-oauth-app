"""
Advanced Analytics Service
Syncs trade data from Deriv API profit_table to Supabase and calculates performance metrics.

Senior Quant Developer Implementation:
- Industry-standard trading metrics
- Efficient data synchronization
- Proper error handling and logging
- Best practices for financial calculations
"""
import requests
from flask import current_app
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import uuid
import threading
from app.supabase_service import SupabaseService, SupabaseServiceError


class AnalyticsService:
    """
    Handles advanced trading analytics and data synchronization from Deriv API.
    Implements institutional-grade performance metrics.
    """
    
    # Deriv WebSocket API endpoint for profit_table
    DERIV_WS_API = 'wss://ws.derivws.com/websockets/v3'
    
    # ==================== DATA SYNCHRONIZATION ====================
    
    @staticmethod
    def sync_trades_from_deriv(user_id: str, access_token: str, 
                               days_back: int = 90, 
                               batch_size: int = 500) -> Dict[str, Any]:
        """
        Sync trade history from Deriv API profit_table to local Supabase trades table.
        
        This implements a full synchronization approach:
        1. Fetch historical trades from Deriv API
        2. Transform data to match local schema
        3. Insert trades that don't exist (based on deriv_transaction_id)
        4. Update existing trades if needed
        
        Args:
            user_id: User UUID from local database
            access_token: Valid Deriv OAuth token
            days_back: Number of days to fetch (default 90 for quarterly analysis)
            batch_size: Records per API call (max 500 per Deriv docs)
            
        Returns:
            dict: {
                'synced': int,
                'skipped': int,
                'errors': int,
                'date_range': {'from': datetime, 'to': datetime}
            }
            
        Raises:
            AnalyticsServiceError: If sync fails
        """
        if not access_token:
            raise AnalyticsServiceError('Missing access token', 'MISSING_TOKEN')
        
        if not user_id:
            raise AnalyticsServiceError('Missing user_id', 'MISSING_USER_ID')
        
        try:
            # Calculate date range for sync
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            current_app.logger.info(f'Starting trade sync for user {user_id}: {start_date} to {end_date}')
            
            # Fetch profit_table data from Deriv API using WebSocket
            # Note: Deriv uses WebSocket for profit_table, not REST
            deriv_trades = AnalyticsService._fetch_profit_table_websocket(
                access_token=access_token,
                date_from=int(start_date.timestamp()),
                date_to=int(end_date.timestamp()),
                limit=batch_size
            )
            
            if not deriv_trades:
                current_app.logger.info('No trades returned from Deriv API')
                return {
                    'synced': 0,
                    'skipped': 0,
                    'errors': 0,
                    'date_range': {'from': start_date, 'to': end_date}
                }
            
            # Transform and insert trades
            synced = 0
            skipped = 0
            errors = 0
            
            for deriv_trade in deriv_trades:
                try:
                    # Check if trade already exists
                    if AnalyticsService._trade_exists(user_id, deriv_trade.get('transaction_id')):
                        skipped += 1
                        continue
                    
                    # Transform Deriv API data to local schema
                    trade_data = AnalyticsService._transform_deriv_trade(deriv_trade, user_id)
                    
                    # Save to Supabase
                    SupabaseService.save_trade(user_id, trade_data)
                    synced += 1
                    
                except Exception as e:
                    current_app.logger.error(f'Failed to sync trade {deriv_trade.get("transaction_id")}: {str(e)}')
                    errors += 1
            
            current_app.logger.info(f'Sync complete: {synced} synced, {skipped} skipped, {errors} errors')
            
            return {
                'synced': synced,
                'skipped': skipped,
                'errors': errors,
                'date_range': {
                    'from': start_date.isoformat(),
                    'to': end_date.isoformat()
                }
            }
            
        except Exception as e:
            current_app.logger.error(f'Trade sync failed: {str(e)}')
            raise AnalyticsServiceError(f'Failed to sync trades: {str(e)}', 'SYNC_FAILED')
    
    @staticmethod
    def _fetch_profit_table_websocket(access_token: str, date_from: int, 
                                     date_to: int, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Fetch profit_table data from Deriv WebSocket API.
        
        Deriv profit_table requires WebSocket connection with authorize flow:
        1. Connect to WebSocket
        2. Send authorize request
        3. Send profit_table request
        4. Receive response
        5. Close connection
        
        Args:
            access_token: OAuth token
            date_from: Unix timestamp
            date_to: Unix timestamp
            limit: Max records per call
            
        Returns:
            list: Trade transaction objects
        """
        import websocket
        import json
        import time
        
        ws_url = 'wss://ws.derivws.com/websockets/v3?app_id=1089'
        response_data = {'transactions': [], 'error': None}
        connection_ready = threading.Event()
        
        def on_message(ws, message):
            """Handle incoming WebSocket messages"""
            try:
                data = json.loads(message)
                msg_type = data.get('msg_type')
                
                current_app.logger.debug(f'WS message: {msg_type}')
                
                if msg_type == 'authorize':
                    # Authorization successful, now request profit_table
                    if data.get('error'):
                        response_data['error'] = data['error']
                        connection_ready.set()
                    else:
                        current_app.logger.info('Authorization successful, requesting profit_table')
                        profit_request = {
                            'profit_table': 1,
                            'date_from': date_from,
                            'date_to': date_to,
                            'limit': limit,
                            'sort': 'DESC'
                        }
                        ws.send(json.dumps(profit_request))
                
                elif msg_type == 'profit_table':
                    # Got profit_table response
                    if data.get('error'):
                        response_data['error'] = data['error']
                    else:
                        profit_table = data.get('profit_table', {})
                        response_data['transactions'] = profit_table.get('transactions', [])
                        current_app.logger.info(f"Received {len(response_data['transactions'])} transactions")
                    
                    connection_ready.set()
                
                elif data.get('error'):
                    response_data['error'] = data['error']
                    connection_ready.set()
                    
            except Exception as e:
                current_app.logger.error(f'Error processing WebSocket message: {str(e)}')
                response_data['error'] = {'message': str(e), 'code': 'PROCESSING_ERROR'}
                connection_ready.set()
        
        def on_error(ws, error):
            """Handle WebSocket errors"""
            current_app.logger.error(f'WebSocket error: {str(error)}')
            response_data['error'] = {'message': str(error), 'code': 'WS_ERROR'}
            connection_ready.set()
        
        def on_close(ws, close_status_code, close_msg):
            """Handle WebSocket close"""
            current_app.logger.debug(f'WebSocket closed: {close_status_code} - {close_msg}')
        
        def on_open(ws):
            """Handle WebSocket open - send authorize request"""
            current_app.logger.info('WebSocket connected, authorizing...')
            auth_request = {
                'authorize': access_token
            }
            ws.send(json.dumps(auth_request))
        
        try:
            # Create WebSocket connection
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # Run WebSocket in a thread
            import threading
            ws_thread = threading.Thread(target=ws.run_forever, kwargs={'ping_interval': 30, 'ping_timeout': 10})
            ws_thread.daemon = True
            ws_thread.start()
            
            # Wait for response (timeout 30 seconds)
            if not connection_ready.wait(timeout=30):
                ws.close()
                raise AnalyticsServiceError('Timeout waiting for profit_table response', 'TIMEOUT')
            
            # Close connection
            ws.close()
            ws_thread.join(timeout=2)
            
            # Check for errors
            if response_data['error']:
                error = response_data['error']
                raise AnalyticsServiceError(
                    f"Deriv API error: {error.get('message', 'Unknown error')}",
                    str(error.get('code', 'API_ERROR'))
                )
            
            return response_data['transactions']
            
        except AnalyticsServiceError:
            raise
        except Exception as e:
            current_app.logger.error(f'Failed to fetch profit_table: {str(e)}')
            raise AnalyticsServiceError(f'Failed to fetch trades from Deriv: {str(e)}', 'API_FETCH_FAILED')
    
    @staticmethod
    def _trade_exists(user_id: str, deriv_transaction_id: str) -> bool:
        """Check if trade already exists in local database"""
        try:
            supabase = SupabaseService.get_client()
            
            result = supabase.table('trades').select('id').eq(
                'user_id', user_id
            ).eq(
                'deriv_transaction_id', deriv_transaction_id
            ).execute()
            
            return len(result.data) > 0
            
        except Exception:
            return False
    
    @staticmethod
    def _transform_deriv_trade(deriv_trade: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Transform Deriv API profit_table transaction to local trades schema.
        
        Deriv API Fields (confirmed from docs):
        - transaction_id (required)
        - contract_id (optional)
        - buy_price (required)
        - sell_price (required)
        - purchase_time (required - epoch)
        - sell_time (optional - epoch)
        - payout (required)
        - profit (calculated: sell_price - buy_price)
        - contract_type (e.g., CALL, PUT, DIGITDIFF)
        - longcode (full contract description)
        - shortcode (compact description)
        - app_id (required)
        
        Args:
            deriv_trade: Transaction object from Deriv API
            user_id: Local user UUID
            
        Returns:
            dict: Trade data matching local schema
        """
        # Extract symbol from longcode or shortcode
        # Example longcode: "Win payout if Volatility 100 Index is strictly higher..."
        # Example shortcode: "CALL_R_100_10.00_1234567890_1234567950_S0P_0"
        symbol = AnalyticsService._extract_symbol(
            deriv_trade.get('longcode', ''),
            deriv_trade.get('shortcode', '')
        )
        
        # Determine direction from contract_type
        contract_type = deriv_trade.get('contract_type', '').upper()
        direction = AnalyticsService._determine_direction(contract_type)
        
        # Calculate PnL
        buy_price = float(deriv_trade.get('buy_price', 0))
        sell_price = float(deriv_trade.get('sell_price', 0))
        pnl = sell_price - buy_price
        
        # Calculate PnL percentage
        pnl_percentage = (pnl / buy_price * 100) if buy_price > 0 else 0
        
        # Determine outcome
        outcome = 'win' if pnl > 0 else 'loss' if pnl < 0 else 'breakeven'
        
        # Convert epoch timestamps to ISO format
        purchase_time = deriv_trade.get('purchase_time')
        sell_time = deriv_trade.get('sell_time')
        
        opened_at = datetime.fromtimestamp(purchase_time).isoformat() if purchase_time else None
        closed_at = datetime.fromtimestamp(sell_time).isoformat() if sell_time else None
        
        # Payout is the potential payout from Deriv
        payout = float(deriv_trade.get('payout', 0))
        
        return {
            'symbol': symbol,
            'contract_type': contract_type,
            'direction': direction,
            'stake': buy_price,  # buy_price is the stake amount
            'entry_price': buy_price,
            'exit_price': sell_price,
            'pnl': pnl,
            'pnl_percentage': pnl_percentage,
            'outcome': outcome,
            'deriv_contract_id': deriv_trade.get('contract_id'),
            'deriv_transaction_id': deriv_trade.get('transaction_id'),
            'opened_at': opened_at,
            'closed_at': closed_at,
            'is_manual': True,  # Synced trades are considered manual (not bot-executed)
            'bot_id': None,  # No bot for historical synced trades
            'trading_system_id': None,  # No system for historical synced trades
            'notes': f'Synced from Deriv API - Payout: {payout}'
        }
    
    @staticmethod
    def _extract_symbol(longcode: str, shortcode: str) -> str:
        """
        Extract trading symbol from longcode or shortcode.
        
        Examples:
        - Longcode: "Win payout if Volatility 100 Index..." -> R_100
        - Shortcode: "CALL_R_100_10.00_..." -> R_100
        """
        # Common Deriv symbols
        symbol_map = {
            'Volatility 10 Index': 'R_10',
            'Volatility 10 (1s) Index': 'R_10',
            'Volatility 25 Index': 'R_25',
            'Volatility 25 (1s) Index': 'R_25',
            'Volatility 50 Index': 'R_50',
            'Volatility 50 (1s) Index': 'R_50',
            'Volatility 75 Index': 'R_75',
            'Volatility 75 (1s) Index': 'R_75',
            'Volatility 100 Index': 'R_100',
            'Volatility 100 (1s) Index': 'R_100',
            'Boom 300 Index': 'BOOM300N',
            'Boom 500 Index': 'BOOM500',
            'Boom 1000 Index': 'BOOM1000',
            'Crash 300 Index': 'CRASH300N',
            'Crash 500 Index': 'CRASH500',
            'Crash 1000 Index': 'CRASH1000',
        }
        
        # Try to match from longcode
        for name, symbol in symbol_map.items():
            if name.lower() in longcode.lower():
                return symbol
        
        # Try to extract from shortcode (format: TYPE_SYMBOL_AMOUNT_...)
        if shortcode and '_' in shortcode:
            parts = shortcode.split('_')
            if len(parts) >= 2:
                # Second part is usually the symbol
                potential_symbol = parts[1]
                if potential_symbol.startswith('R_') or potential_symbol.startswith('frx'):
                    return potential_symbol
        
        # Default fallback
        return 'UNKNOWN'
    
    @staticmethod
    def _determine_direction(contract_type: str) -> str:
        """
        Determine trade direction from contract type.
        
        Args:
            contract_type: Deriv contract type (CALL, PUT, DIGITDIFF, etc.)
            
        Returns:
            str: 'buy' or 'sell'
        """
        # Options: CALL is bullish (buy), PUT is bearish (sell)
        if contract_type in ['CALL', 'CALLE', 'ASIANU', 'DIGITOVER']:
            return 'buy'
        elif contract_type in ['PUT', 'PUTE', 'ASIAND', 'DIGITUNDER']:
            return 'sell'
        else:
            # Default to buy for unknown types
            return 'buy'
    
    # ==================== PERFORMANCE METRICS ====================
    
    @staticmethod
    def calculate_win_rate(user_id: str, timeframe: str = 'all', 
                          symbol: Optional[str] = None,
                          trading_system_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate win rate: percentage of winning trades.
        
        Formula: (Number of Wins / Total Closed Trades) × 100
        
        Industry standard metric for trading performance.
        
        Args:
            user_id: User UUID
            timeframe: 'hourly', 'daily', 'all'
            symbol: Filter by specific symbol
            trading_system_id: Filter by trading system
            
        Returns:
            dict: {
                'win_rate': float,
                'total_trades': int,
                'winning_trades': int,
                'losing_trades': int,
                'breakeven_trades': int
            }
        """
        try:
            trades = AnalyticsService._get_filtered_trades(
                user_id, timeframe, symbol, trading_system_id
            )
            
            if not trades:
                return {
                    'win_rate': 0.0,
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'breakeven_trades': 0
                }
            
            # Filter only closed trades
            closed_trades = [t for t in trades if t.get('outcome') != 'open']
            
            total_trades = len(closed_trades)
            if total_trades == 0:
                return {
                    'win_rate': 0.0,
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'breakeven_trades': 0
                }
            
            winning_trades = len([t for t in closed_trades if t.get('outcome') == 'win'])
            losing_trades = len([t for t in closed_trades if t.get('outcome') == 'loss'])
            breakeven_trades = len([t for t in closed_trades if t.get('outcome') == 'breakeven'])
            
            win_rate = (winning_trades / total_trades) * 100
            
            return {
                'win_rate': round(win_rate, 2),
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': breakeven_trades
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to calculate win rate: {str(e)}')
            raise AnalyticsServiceError('Failed to calculate win rate', 'CALC_FAILED')
    
    @staticmethod
    def calculate_profit_factor(user_id: str, timeframe: str = 'all',
                               symbol: Optional[str] = None,
                               trading_system_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate profit factor: ratio of gross profits to gross losses.
        
        Formula: Gross Profit / Gross Loss
        
        Industry interpretation:
        - PF > 2.0: Excellent
        - PF 1.5-2.0: Very good
        - PF 1.25-1.5: Good
        - PF 1.0-1.25: Mediocre
        - PF < 1.0: Losing system
        
        Args:
            user_id: User UUID
            timeframe: 'hourly', 'daily', 'all'
            symbol: Filter by specific symbol
            trading_system_id: Filter by trading system
            
        Returns:
            dict: {
                'profit_factor': float,
                'gross_profit': float,
                'gross_loss': float,
                'rating': str
            }
        """
        try:
            trades = AnalyticsService._get_filtered_trades(
                user_id, timeframe, symbol, trading_system_id
            )
            
            if not trades:
                return {
                    'profit_factor': 0.0,
                    'gross_profit': 0.0,
                    'gross_loss': 0.0,
                    'rating': 'insufficient_data'
                }
            
            # Calculate gross profit and gross loss
            gross_profit = sum(
                float(t.get('pnl', 0)) for t in trades 
                if float(t.get('pnl', 0)) > 0 and t.get('outcome') != 'open'
            )
            
            gross_loss = abs(sum(
                float(t.get('pnl', 0)) for t in trades 
                if float(t.get('pnl', 0)) < 0 and t.get('outcome') != 'open'
            ))
            
            # Calculate profit factor
            if gross_loss == 0:
                profit_factor = gross_profit if gross_profit > 0 else 0.0
            else:
                profit_factor = gross_profit / gross_loss
            
            # Rate the profit factor
            if profit_factor >= 2.0:
                rating = 'excellent'
            elif profit_factor >= 1.5:
                rating = 'very_good'
            elif profit_factor >= 1.25:
                rating = 'good'
            elif profit_factor >= 1.0:
                rating = 'mediocre'
            else:
                rating = 'losing'
            
            return {
                'profit_factor': round(profit_factor, 2),
                'gross_profit': round(gross_profit, 2),
                'gross_loss': round(gross_loss, 2),
                'rating': rating
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to calculate profit factor: {str(e)}')
            raise AnalyticsServiceError('Failed to calculate profit factor', 'CALC_FAILED')
    
    @staticmethod
    def calculate_max_drawdown(user_id: str, timeframe: str = 'all',
                              symbol: Optional[str] = None,
                              trading_system_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate maximum drawdown: worst peak-to-trough decline in account equity.
        
        Formula: ((Trough Value - Peak Value) / Peak Value) × 100
        
        Industry standard risk metric. Lower is better.
        Professional traders aim to keep max drawdown below 20%.
        
        Args:
            user_id: User UUID
            timeframe: 'hourly', 'daily', 'all'
            symbol: Filter by specific symbol
            trading_system_id: Filter by trading system
            
        Returns:
            dict: {
                'max_drawdown_pct': float,
                'max_drawdown_amount': float,
                'peak_balance': float,
                'trough_balance': float,
                'recovery_status': str
            }
        """
        try:
            trades = AnalyticsService._get_filtered_trades(
                user_id, timeframe, symbol, trading_system_id
            )
            
            if not trades:
                return {
                    'max_drawdown_pct': 0.0,
                    'max_drawdown_amount': 0.0,
                    'peak_balance': 0.0,
                    'trough_balance': 0.0,
                    'recovery_status': 'no_data'
                }
            
            # Sort trades by time
            sorted_trades = sorted(
                trades,
                key=lambda t: t.get('opened_at', datetime.min.isoformat())
            )
            
            # Calculate running balance and track drawdowns
            running_balance = 0.0
            peak_balance = 0.0
            max_drawdown = 0.0
            max_drawdown_amount = 0.0
            trough_balance = 0.0
            
            for trade in sorted_trades:
                pnl = float(trade.get('pnl', 0))
                running_balance += pnl
                
                # Update peak if we hit a new high
                if running_balance > peak_balance:
                    peak_balance = running_balance
                
                # Calculate current drawdown from peak
                current_drawdown = running_balance - peak_balance
                
                # Update max drawdown if current is worse
                if current_drawdown < max_drawdown:
                    max_drawdown = current_drawdown
                    max_drawdown_amount = abs(max_drawdown)
                    trough_balance = running_balance
            
            # Calculate drawdown percentage
            max_drawdown_pct = (max_drawdown / peak_balance * 100) if peak_balance > 0 else 0.0
            
            # Determine recovery status
            if running_balance >= peak_balance:
                recovery_status = 'recovered'
            elif running_balance > trough_balance:
                recovery_status = 'recovering'
            else:
                recovery_status = 'in_drawdown'
            
            return {
                'max_drawdown_pct': round(abs(max_drawdown_pct), 2),
                'max_drawdown_amount': round(max_drawdown_amount, 2),
                'peak_balance': round(peak_balance, 2),
                'trough_balance': round(trough_balance, 2),
                'current_balance': round(running_balance, 2),
                'recovery_status': recovery_status
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to calculate max drawdown: {str(e)}')
            raise AnalyticsServiceError('Failed to calculate max drawdown', 'CALC_FAILED')
    
    @staticmethod
    def calculate_expectancy(user_id: str, timeframe: str = 'all',
                            symbol: Optional[str] = None,
                            trading_system_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate expectancy: average amount you can expect to win (or lose) per trade.
        
        Formula: (Win Rate × Average Win) - (Loss Rate × Average Loss)
        
        Industry interpretation:
        - Positive expectancy: System has edge
        - Higher expectancy: Better system
        - Should be significantly positive to cover costs and slippage
        
        Args:
            user_id: User UUID
            timeframe: 'hourly', 'daily', 'all'
            symbol: Filter by specific symbol
            trading_system_id: Filter by trading system
            
        Returns:
            dict: {
                'expectancy': float,
                'average_win': float,
                'average_loss': float,
                'expected_value_per_trade': float,
                'assessment': str
            }
        """
        try:
            trades = AnalyticsService._get_filtered_trades(
                user_id, timeframe, symbol, trading_system_id
            )
            
            if not trades:
                return {
                    'expectancy': 0.0,
                    'average_win': 0.0,
                    'average_loss': 0.0,
                    'expected_value_per_trade': 0.0,
                    'assessment': 'insufficient_data'
                }
            
            # Filter closed trades
            closed_trades = [t for t in trades if t.get('outcome') != 'open']
            
            if not closed_trades:
                return {
                    'expectancy': 0.0,
                    'average_win': 0.0,
                    'average_loss': 0.0,
                    'expected_value_per_trade': 0.0,
                    'assessment': 'no_closed_trades'
                }
            
            # Separate winning and losing trades
            winning_trades = [t for t in closed_trades if float(t.get('pnl', 0)) > 0]
            losing_trades = [t for t in closed_trades if float(t.get('pnl', 0)) < 0]
            
            total_trades = len(closed_trades)
            
            # Calculate win rate and loss rate
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
            loss_rate = len(losing_trades) / total_trades if total_trades > 0 else 0
            
            # Calculate average win and average loss
            average_win = (
                sum(float(t.get('pnl', 0)) for t in winning_trades) / len(winning_trades)
                if winning_trades else 0
            )
            
            average_loss = (
                abs(sum(float(t.get('pnl', 0)) for t in losing_trades) / len(losing_trades))
                if losing_trades else 0
            )
            
            # Calculate expectancy
            expectancy = (win_rate * average_win) - (loss_rate * average_loss)
            
            # Assess the expectancy
            if expectancy > 1.0:
                assessment = 'excellent'
            elif expectancy > 0.5:
                assessment = 'good'
            elif expectancy > 0:
                assessment = 'positive'
            elif expectancy == 0:
                assessment = 'breakeven'
            else:
                assessment = 'negative'
            
            return {
                'expectancy': round(expectancy, 2),
                'average_win': round(average_win, 2),
                'average_loss': round(average_loss, 2),
                'expected_value_per_trade': round(expectancy, 2),
                'win_rate': round(win_rate * 100, 2),
                'loss_rate': round(loss_rate * 100, 2),
                'assessment': assessment
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to calculate expectancy: {str(e)}')
            raise AnalyticsServiceError('Failed to calculate expectancy', 'CALC_FAILED')
    
    # ==================== HELPER METHODS ====================
    
    @staticmethod
    def _get_filtered_trades(user_id: str, timeframe: str = 'all',
                            symbol: Optional[str] = None,
                            trading_system_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get trades filtered by timeframe, symbol, and trading system.
        
        Args:
            user_id: User UUID
            timeframe: 'hourly', 'daily', 'all'
            symbol: Filter by specific symbol
            trading_system_id: Filter by trading system
            
        Returns:
            list: Filtered trades
        """
        try:
            supabase = SupabaseService.get_client()
            
            # Start with base query
            query = supabase.table('trades').select('*').eq('user_id', user_id)
            
            # Apply timeframe filter
            if timeframe == 'hourly':
                cutoff = datetime.utcnow() - timedelta(hours=1)
                query = query.gte('opened_at', cutoff.isoformat())
            elif timeframe == 'daily':
                cutoff = datetime.utcnow() - timedelta(days=1)
                query = query.gte('opened_at', cutoff.isoformat())
            # 'all' requires no time filter
            
            # Apply symbol filter
            if symbol:
                query = query.eq('symbol', symbol)
            
            # Apply trading system filter
            if trading_system_id:
                query = query.eq('trading_system_id', trading_system_id)
            
            # Order by time
            result = query.order('opened_at', desc=False).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            current_app.logger.error(f'Failed to get filtered trades: {str(e)}')
            return []
    
    @staticmethod
    def get_analytics_overview(user_id: str, timeframe: str = 'all',
                              symbol: Optional[str] = None,
                              trading_system_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive analytics overview with all metrics.
        
        Args:
            user_id: User UUID
            timeframe: 'hourly', 'daily', 'all'
            symbol: Filter by specific symbol
            trading_system_id: Filter by trading system
            
        Returns:
            dict: Complete analytics dashboard data
        """
        try:
            win_rate = AnalyticsService.calculate_win_rate(
                user_id, timeframe, symbol, trading_system_id
            )
            
            profit_factor = AnalyticsService.calculate_profit_factor(
                user_id, timeframe, symbol, trading_system_id
            )
            
            max_drawdown = AnalyticsService.calculate_max_drawdown(
                user_id, timeframe, symbol, trading_system_id
            )
            
            expectancy = AnalyticsService.calculate_expectancy(
                user_id, timeframe, symbol, trading_system_id
            )
            
            # Get additional summary stats
            trades = AnalyticsService._get_filtered_trades(
                user_id, timeframe, symbol, trading_system_id
            )
            
            total_pnl = sum(float(t.get('pnl', 0)) for t in trades)
            
            return {
                'timeframe': timeframe,
                'symbol': symbol,
                'trading_system_id': trading_system_id,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown,
                'expectancy': expectancy,
                'summary': {
                    'total_trades': len(trades),
                    'total_pnl': round(total_pnl, 2)
                }
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to get analytics overview: {str(e)}')
            raise AnalyticsServiceError('Failed to get analytics overview', 'OVERVIEW_FAILED')


class AnalyticsServiceError(Exception):
    """Custom exception for analytics service errors"""
    
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

    
    # ==================== ADVANCED CHART DATA ====================
    
    @staticmethod
    def get_equity_curve(user_id: str, timeframe: str = '1D') -> Dict[str, Any]:
        """
        Generate equity curve data for TradingView Lightweight Charts.
        
        Equity curve shows cumulative P/L over time - the most important chart
        for quantitative traders to visualize account growth/decline.
        
        Uses SQL window functions for efficient cumulative calculation.
        
        Args:
            user_id: User UUID
            timeframe: '1H', '4H', '1D', '1W', '1M', 'All'
            
        Returns:
            dict: {
                'data': [{'time': timestamp, 'value': cumulative_pnl}, ...],
                'current_balance': float,
                'peak_balance': float,
                'total_pnl': float,
                'timeframe': str
            }
        """
        try:
            # Get date range based on timeframe
            end_date = datetime.utcnow()
            
            timeframe_map = {
                '1H': timedelta(hours=1),
                '4H': timedelta(hours=4),
                '1D': timedelta(days=1),
                '1W': timedelta(weeks=1),
                '1M': timedelta(days=30),
                'All': None  # All time
            }
            
            start_date = None
            if timeframe in timeframe_map and timeframe_map[timeframe]:
                start_date = end_date - timeframe_map[timeframe]
            
            # Fetch trades with cumulative sum using raw SQL for efficiency
            supabase = SupabaseService.get_client()
            
            # Build query
            query = supabase.table('trades').select(
                'closed_at, pnl, opened_at'
            ).eq('user_id', user_id).not_.is_('closed_at', 'null').order('closed_at')
            
            if start_date:
                query = query.gte('closed_at', start_date.isoformat())
            
            result = query.execute()
            trades = result.data
            
            if not trades:
                return {
                    'data': [],
                    'current_balance': 0.0,
                    'peak_balance': 0.0,
                    'total_pnl': 0.0,
                    'timeframe': timeframe
                }
            
            # Calculate cumulative P/L
            cumulative_pnl = 0.0
            peak_balance = 0.0
            equity_data = []
            
            for trade in trades:
                pnl = float(trade.get('pnl', 0))
                cumulative_pnl += pnl
                
                # Track peak
                if cumulative_pnl > peak_balance:
                    peak_balance = cumulative_pnl
                
                # Convert timestamp to epoch for TradingView
                closed_at = trade.get('closed_at')
                if closed_at:
                    timestamp = int(datetime.fromisoformat(closed_at.replace('Z', '+00:00')).timestamp())
                    
                    equity_data.append({
                        'time': timestamp,
                        'value': round(cumulative_pnl, 2)
                    })
            
            return {
                'data': equity_data,
                'current_balance': round(cumulative_pnl, 2),
                'peak_balance': round(peak_balance, 2),
                'total_pnl': round(cumulative_pnl, 2),
                'timeframe': timeframe,
                'total_trades': len(trades)
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to generate equity curve: {str(e)}')
            raise AnalyticsServiceError('Failed to generate equity curve', 'CHART_FAILED')
    
    @staticmethod
    def get_daily_pnl_chart(user_id: str, timeframe: str = '1M') -> Dict[str, Any]:
        """
        Generate daily P/L bar chart data.
        
        Shows profit/loss per day as green (profit) or red (loss) bars.
        Essential for identifying profitable vs losing days.
        
        Args:
            user_id: User UUID
            timeframe: '1W', '1M', '3M', 'All'
            
        Returns:
            dict: {
                'data': [{'date': 'YYYY-MM-DD', 'pnl': float, 'trades': int}, ...],
                'total_profit_days': int,
                'total_loss_days': int,
                'best_day': float,
                'worst_day': float
            }
        """
        try:
            # Get date range
            end_date = datetime.utcnow()
            
            timeframe_map = {
                '1W': timedelta(weeks=1),
                '1M': timedelta(days=30),
                '3M': timedelta(days=90),
                'All': None
            }
            
            start_date = None
            if timeframe in timeframe_map and timeframe_map[timeframe]:
                start_date = end_date - timeframe_map[timeframe]
            
            # Fetch trades
            supabase = SupabaseService.get_client()
            
            query = supabase.table('trades').select(
                'closed_at, pnl'
            ).eq('user_id', user_id).not_.is_('closed_at', 'null').order('closed_at')
            
            if start_date:
                query = query.gte('closed_at', start_date.isoformat())
            
            result = query.execute()
            trades = result.data
            
            if not trades:
                return {
                    'data': [],
                    'total_profit_days': 0,
                    'total_loss_days': 0,
                    'best_day': 0.0,
                    'worst_day': 0.0
                }
            
            # Group by day
            daily_pnl = {}
            
            for trade in trades:
                closed_at = trade.get('closed_at')
                pnl = float(trade.get('pnl', 0))
                
                if closed_at:
                    # Extract date (YYYY-MM-DD)
                    date_obj = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    date_key = date_obj.strftime('%Y-%m-%d')
                    
                    if date_key not in daily_pnl:
                        daily_pnl[date_key] = {'pnl': 0.0, 'trades': 0}
                    
                    daily_pnl[date_key]['pnl'] += pnl
                    daily_pnl[date_key]['trades'] += 1
            
            # Convert to array and calculate stats
            chart_data = []
            profit_days = 0
            loss_days = 0
            best_day = 0.0
            worst_day = 0.0
            
            for date_key in sorted(daily_pnl.keys()):
                day_data = daily_pnl[date_key]
                pnl = round(day_data['pnl'], 2)
                
                chart_data.append({
                    'date': date_key,
                    'pnl': pnl,
                    'trades': day_data['trades']
                })
                
                # Update stats
                if pnl > 0:
                    profit_days += 1
                    if pnl > best_day:
                        best_day = pnl
                elif pnl < 0:
                    loss_days += 1
                    if pnl < worst_day:
                        worst_day = pnl
            
            return {
                'data': chart_data,
                'total_profit_days': profit_days,
                'total_loss_days': loss_days,
                'best_day': round(best_day, 2),
                'worst_day': round(worst_day, 2),
                'timeframe': timeframe
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to generate daily P/L chart: {str(e)}')
            raise AnalyticsServiceError('Failed to generate daily P/L chart', 'CHART_FAILED')
    
    @staticmethod
    def get_symbol_performance(user_id: str, timeframe: str = 'all') -> Dict[str, Any]:
        """
        Get performance breakdown by trading symbol.
        
        Returns sortable table data showing which symbols are most profitable.
        Critical for identifying which instruments to focus on.
        
        Args:
            user_id: User UUID
            timeframe: 'all', 'daily', 'hourly'
            
        Returns:
            dict: {
                'data': [{
                    'symbol': str,
                    'trades': int,
                    'win_rate': float,
                    'total_pnl': float,
                    'avg_pnl': float,
                    'profit_factor': float
                }, ...],
                'total_symbols': int
            }
        """
        try:
            trades = AnalyticsService._get_filtered_trades(user_id, timeframe)
            
            if not trades:
                return {'data': [], 'total_symbols': 0}
            
            # Group by symbol
            symbol_stats = {}
            
            for trade in trades:
                symbol = trade.get('symbol', 'UNKNOWN')
                pnl = float(trade.get('pnl', 0))
                outcome = trade.get('outcome', 'open')
                
                if symbol not in symbol_stats:
                    symbol_stats[symbol] = {
                        'symbol': symbol,
                        'trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'total_pnl': 0.0,
                        'gross_profit': 0.0,
                        'gross_loss': 0.0
                    }
                
                stats = symbol_stats[symbol]
                
                if outcome != 'open':
                    stats['trades'] += 1
                    stats['total_pnl'] += pnl
                    
                    if outcome == 'win':
                        stats['wins'] += 1
                        stats['gross_profit'] += pnl
                    elif outcome == 'loss':
                        stats['losses'] += 1
                        stats['gross_loss'] += abs(pnl)
            
            # Calculate derived metrics
            result_data = []
            
            for symbol, stats in symbol_stats.items():
                if stats['trades'] == 0:
                    continue
                
                win_rate = (stats['wins'] / stats['trades']) * 100 if stats['trades'] > 0 else 0
                avg_pnl = stats['total_pnl'] / stats['trades'] if stats['trades'] > 0 else 0
                
                profit_factor = (
                    stats['gross_profit'] / stats['gross_loss'] 
                    if stats['gross_loss'] > 0 else stats['gross_profit']
                )
                
                result_data.append({
                    'symbol': symbol,
                    'trades': stats['trades'],
                    'win_rate': round(win_rate, 2),
                    'total_pnl': round(stats['total_pnl'], 2),
                    'avg_pnl': round(avg_pnl, 2),
                    'profit_factor': round(profit_factor, 2)
                })
            
            # Sort by total P/L descending
            result_data.sort(key=lambda x: x['total_pnl'], reverse=True)
            
            return {
                'data': result_data,
                'total_symbols': len(result_data),
                'timeframe': timeframe
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to get symbol performance: {str(e)}')
            raise AnalyticsServiceError('Failed to get symbol performance', 'ANALYSIS_FAILED')
    
    @staticmethod
    def get_top_strategies(user_id: str, timeframe: str = 'all', limit: int = 10) -> Dict[str, Any]:
        """
        Get top performing trading systems (strategies).
        
        Returns leaderboard of strategies sorted by performance metrics.
        Essential for identifying which systems to allocate more capital to.
        
        Args:
            user_id: User UUID
            timeframe: 'all', 'daily', 'hourly'
            limit: Max number of strategies to return
            
        Returns:
            dict: {
                'data': [{
                    'strategy_id': str,
                    'strategy_name': str,
                    'trades': int,
                    'win_rate': float,
                    'total_pnl': float,
                    'profit_factor': float,
                    'expectancy': float
                }, ...],
                'total_strategies': int
            }
        """
        try:
            trades = AnalyticsService._get_filtered_trades(user_id, timeframe)
            
            if not trades:
                return {'data': [], 'total_strategies': 0}
            
            # Group by trading_system_id
            strategy_stats = {}
            
            for trade in trades:
                system_id = trade.get('trading_system_id')
                if not system_id:
                    continue  # Skip trades without trading system
                
                pnl = float(trade.get('pnl', 0))
                outcome = trade.get('outcome', 'open')
                
                if system_id not in strategy_stats:
                    strategy_stats[system_id] = {
                        'strategy_id': system_id,
                        'trades': 0,
                        'wins': 0,
                        'losses': 0,
                        'total_pnl': 0.0,
                        'gross_profit': 0.0,
                        'gross_loss': 0.0,
                        'win_pnls': [],
                        'loss_pnls': []
                    }
                
                stats = strategy_stats[system_id]
                
                if outcome != 'open':
                    stats['trades'] += 1
                    stats['total_pnl'] += pnl
                    
                    if outcome == 'win':
                        stats['wins'] += 1
                        stats['gross_profit'] += pnl
                        stats['win_pnls'].append(pnl)
                    elif outcome == 'loss':
                        stats['losses'] += 1
                        stats['gross_loss'] += abs(pnl)
                        stats['loss_pnls'].append(abs(pnl))
            
            # Fetch strategy names from database
            supabase = SupabaseService.get_client()
            result_data = []
            
            for system_id, stats in strategy_stats.items():
                if stats['trades'] == 0:
                    continue
                
                # Get strategy name
                try:
                    strategy_result = supabase.table('trading_systems').select('name').eq('id', system_id).execute()
                    strategy_name = strategy_result.data[0]['name'] if strategy_result.data else 'Unknown Strategy'
                except:
                    strategy_name = 'Unknown Strategy'
                
                # Calculate metrics
                win_rate = (stats['wins'] / stats['trades']) * 100 if stats['trades'] > 0 else 0
                
                profit_factor = (
                    stats['gross_profit'] / stats['gross_loss']
                    if stats['gross_loss'] > 0 else stats['gross_profit']
                )
                
                # Calculate expectancy
                avg_win = sum(stats['win_pnls']) / len(stats['win_pnls']) if stats['win_pnls'] else 0
                avg_loss = sum(stats['loss_pnls']) / len(stats['loss_pnls']) if stats['loss_pnls'] else 0
                win_rate_decimal = win_rate / 100
                loss_rate = 1 - win_rate_decimal
                expectancy = (win_rate_decimal * avg_win) - (loss_rate * avg_loss)
                
                result_data.append({
                    'strategy_id': system_id,
                    'strategy_name': strategy_name,
                    'trades': stats['trades'],
                    'win_rate': round(win_rate, 2),
                    'total_pnl': round(stats['total_pnl'], 2),
                    'profit_factor': round(profit_factor, 2),
                    'expectancy': round(expectancy, 2)
                })
            
            # Sort by total P/L descending
            result_data.sort(key=lambda x: x['total_pnl'], reverse=True)
            
            # Apply limit
            result_data = result_data[:limit]
            
            return {
                'data': result_data,
                'total_strategies': len(strategy_stats),
                'timeframe': timeframe
            }
            
        except Exception as e:
            current_app.logger.error(f'Failed to get top strategies: {str(e)}')
            raise AnalyticsServiceError('Failed to get top strategies', 'ANALYSIS_FAILED')
