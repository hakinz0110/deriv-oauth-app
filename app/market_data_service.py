import websocket
import json
import threading
from flask import current_app

class MarketDataService:
    """
    Handles public market data WebSocket connections.
    No authentication required for public market data.
    """
    
    # Public WebSocket endpoint - no authentication required
    PUBLIC_WS_URL = 'wss://api.derivws.com/trading/v1/options/ws/public'
    
    @staticmethod
    def create_connection(on_message=None, on_error=None, on_close=None, on_open=None):
        """
        Create a WebSocket connection to the public market data endpoint.
        
        Args:
            on_message: Callback for message events (receives ws, message)
            on_error: Callback for error events (receives ws, error)
            on_close: Callback for close events (receives ws, close_status_code, close_msg)
            on_open: Callback for open events (receives ws)
            
        Returns:
            websocket.WebSocketApp: WebSocket application instance
            
        Raises:
            MarketDataServiceError: If connection setup fails
        """
        try:
            ws = websocket.WebSocketApp(
                MarketDataService.PUBLIC_WS_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            current_app.logger.info('Created public market data WebSocket connection')
            return ws
            
        except Exception as e:
            current_app.logger.error(f'Public WebSocket connection setup failed: {type(e).__name__}')
            raise MarketDataServiceError('Failed to create market data connection', 'CONNECTION_SETUP_FAILED')
    
    @staticmethod
    def send_message(ws, message):
        """
        Send a JSON message through the WebSocket connection.
        
        Args:
            ws: WebSocket connection
            message: Dictionary to send as JSON
            
        Raises:
            MarketDataServiceError: If send fails
        """
        try:
            message_json = json.dumps(message)
            ws.send(message_json)
            current_app.logger.debug(f'Sent market data message: {message.get("msg_type", "unknown")}')
        except Exception as e:
            current_app.logger.error(f'Market data WebSocket send failed: {type(e).__name__}')
            raise MarketDataServiceError('Failed to send message', 'SEND_FAILED')
    
    @staticmethod
    def subscribe_ticks(ws, symbol):
        """
        Subscribe to tick data for a symbol.
        
        Args:
            ws: WebSocket connection
            symbol: Trading symbol (e.g., 'R_10', '1HZ100V')
            
        Raises:
            MarketDataServiceError: If subscription fails
        """
        message = {
            'ticks': symbol,
            'subscribe': 1
        }
        MarketDataService.send_message(ws, message)
    
    @staticmethod
    def subscribe_candles(ws, symbol, style='candles', granularity=60):
        """
        Subscribe to candle/OHLC data for a symbol.
        
        Args:
            ws: WebSocket connection
            symbol: Trading symbol
            style: 'candles' for standard candles
            granularity: Candle interval in seconds (60, 120, 180, 300, 600, 900, 1800, 3600, etc.)
            
        Raises:
            MarketDataServiceError: If subscription fails
        """
        message = {
            'ticks_history': symbol,
            'style': style,
            'granularity': granularity,
            'subscribe': 1
        }
        MarketDataService.send_message(ws, message)
    
    @staticmethod
    def get_active_symbols(ws, product_type='basic'):
        """
        Request list of active trading symbols.
        
        Args:
            ws: WebSocket connection
            product_type: 'basic' or 'full'
            
        Raises:
            MarketDataServiceError: If request fails
        """
        message = {
            'active_symbols': product_type
        }
        MarketDataService.send_message(ws, message)
    
    @staticmethod
    def unsubscribe_ticks(ws, subscription_id):
        """
        Unsubscribe from a tick stream.
        
        Args:
            ws: WebSocket connection
            subscription_id: ID returned in subscription response
            
        Raises:
            MarketDataServiceError: If unsubscribe fails
        """
        message = {
            'forget': subscription_id
        }
        MarketDataService.send_message(ws, message)
    
    @staticmethod
    def run_connection(ws):
        """
        Run the WebSocket connection in a blocking manner.
        
        Args:
            ws: WebSocket connection
            
        Raises:
            MarketDataServiceError: If connection fails
        """
        try:
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            current_app.logger.error(f'Market data WebSocket run failed: {type(e).__name__}')
            raise MarketDataServiceError('WebSocket connection failed', 'CONNECTION_FAILED')
    
    @staticmethod
    def run_connection_threaded(ws):
        """
        Run the WebSocket connection in a separate thread.
        
        Args:
            ws: WebSocket connection
            
        Returns:
            threading.Thread: Thread running the WebSocket connection
        """
        thread = threading.Thread(
            target=ws.run_forever,
            kwargs={'ping_interval': 30, 'ping_timeout': 10}
        )
        thread.daemon = True
        thread.start()
        current_app.logger.info('Market data WebSocket running in background thread')
        return thread
    
    @staticmethod
    def close_connection(ws):
        """
        Close the WebSocket connection safely.
        
        Args:
            ws: WebSocket connection
        """
        try:
            ws.close()
            current_app.logger.info('Closed market data WebSocket connection')
        except Exception as e:
            current_app.logger.error(f'Market data WebSocket close failed: {type(e).__name__}')
    
    @staticmethod
    def parse_message(message_json):
        """
        Parse and validate a WebSocket message.
        
        Args:
            message_json: JSON string from WebSocket
            
        Returns:
            dict: Parsed message
            
        Raises:
            MarketDataServiceError: If parsing fails
        """
        try:
            return json.loads(message_json)
        except json.JSONDecodeError as e:
            current_app.logger.error(f'Failed to parse WebSocket message: {str(e)}')
            raise MarketDataServiceError('Invalid message format', 'PARSE_ERROR')


class MarketDataServiceError(Exception):
    """
    Custom exception for market data service errors.
    Provides user-friendly error messages.
    """
    
    def __init__(self, message, error_code):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert error to dictionary for JSON response."""
        return {
            'error': self.error_code,
            'message': self.message
        }
