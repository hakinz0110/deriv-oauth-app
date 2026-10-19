import requests
import websocket
import json
import threading
from flask import current_app

class WebSocketService:
    """
    Handles authenticated WebSocket connections for Deriv trading.
    Uses OTP-authenticated WebSocket URLs for account-specific trading.
    """
    
    # Deriv API endpoint for OTP request
    OTP_ENDPOINT_TEMPLATE = 'https://api.derivws.com/trading/v1/options/accounts/{accountId}/otp'
    
    @staticmethod
    def request_websocket_url(account_id, access_token):
        """
        Request an OTP-authenticated WebSocket URL for a specific account.
        
        Args:
            account_id: The account ID to connect to
            access_token: Valid OAuth access token
            
        Returns:
            str: WebSocket URL with embedded OTP
            
        Raises:
            WebSocketServiceError: If OTP request fails
        """
        if not account_id:
            raise WebSocketServiceError('Missing account ID', 'MISSING_ACCOUNT_ID')
        
        if not access_token:
            raise WebSocketServiceError('Missing access token', 'MISSING_TOKEN')
        
        # Build OTP endpoint URL
        otp_url = WebSocketService.OTP_ENDPOINT_TEMPLATE.format(accountId=account_id)
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                otp_url,
                headers=headers,
                timeout=10
            )
            
            # Check for unsuccessful response
            if response.status_code == 401:
                raise WebSocketServiceError('Authentication failed - token may be invalid or expired', 'INVALID_TOKEN')
            elif response.status_code == 403:
                raise WebSocketServiceError('Access forbidden - insufficient permissions', 'FORBIDDEN')
            elif response.status_code == 404:
                raise WebSocketServiceError('Account not found or OTP endpoint unavailable', 'NOT_FOUND')
            elif response.status_code >= 500:
                raise WebSocketServiceError('Deriv API server error', 'SERVER_ERROR')
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            ws_url = data.get('data', {}).get('url')
            
            if not ws_url:
                raise WebSocketServiceError('WebSocket URL not found in response', 'INVALID_RESPONSE')
            
            # Log success without exposing token or OTP
            current_app.logger.info(f'Obtained WebSocket URL for account {account_id}')
            
            return ws_url
            
        except requests.exceptions.Timeout:
            raise WebSocketServiceError('Request timeout - Deriv API did not respond', 'TIMEOUT')
        except requests.exceptions.ConnectionError:
            raise WebSocketServiceError('Connection error - unable to reach Deriv API', 'CONNECTION_ERROR')
        except requests.exceptions.RequestException as e:
            # Log error without exposing token
            current_app.logger.error(f'OTP request failed: {type(e).__name__}')
            raise WebSocketServiceError('Failed to obtain WebSocket URL', 'REQUEST_FAILED')
        except (ValueError, KeyError) as e:
            # JSON parsing error
            current_app.logger.error(f'Invalid JSON response from OTP API: {str(e)}')
            raise WebSocketServiceError('Invalid response from Deriv API', 'INVALID_RESPONSE')
    
    @staticmethod
    def create_connection(ws_url, on_message=None, on_error=None, on_close=None, on_open=None):
        """
        Create a WebSocket connection to the authenticated trading endpoint.
        
        Args:
            ws_url: OTP-authenticated WebSocket URL from request_websocket_url()
            on_message: Callback for message events
            on_error: Callback for error events
            on_close: Callback for close events
            on_open: Callback for open events
            
        Returns:
            websocket.WebSocketApp: WebSocket application instance
            
        Raises:
            WebSocketServiceError: If connection setup fails
        """
        if not ws_url:
            raise WebSocketServiceError('Missing WebSocket URL', 'MISSING_URL')
        
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            return ws
            
        except Exception as e:
            current_app.logger.error(f'WebSocket connection setup failed: {type(e).__name__}')
            raise WebSocketServiceError('Failed to create WebSocket connection', 'CONNECTION_SETUP_FAILED')
    
    @staticmethod
    def send_message(ws, message):
        """
        Send a JSON message through the WebSocket connection.
        
        Args:
            ws: WebSocket connection
            message: Dictionary to send as JSON
            
        Raises:
            WebSocketServiceError: If send fails
        """
        try:
            ws.send(json.dumps(message))
        except Exception as e:
            current_app.logger.error(f'WebSocket send failed: {type(e).__name__}')
            raise WebSocketServiceError('Failed to send message', 'SEND_FAILED')
    
    @staticmethod
    def run_connection(ws, timeout=None):
        """
        Run the WebSocket connection in a blocking manner.
        
        Args:
            ws: WebSocket connection
            timeout: Connection timeout in seconds (optional)
            
        Raises:
            WebSocketServiceError: If connection fails
        """
        try:
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            current_app.logger.error(f'WebSocket run failed: {type(e).__name__}')
            raise WebSocketServiceError('WebSocket connection failed', 'CONNECTION_FAILED')
    
    @staticmethod
    def run_connection_threaded(ws):
        """
        Run the WebSocket connection in a separate thread.
        
        Args:
            ws: WebSocket connection
            
        Returns:
            threading.Thread: Thread running the WebSocket connection
        """
        thread = threading.Thread(target=ws.run_forever, kwargs={'ping_interval': 30, 'ping_timeout': 10})
        thread.daemon = True
        thread.start()
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
        except Exception as e:
            current_app.logger.error(f'WebSocket close failed: {type(e).__name__}')


class WebSocketServiceError(Exception):
    """
    Custom exception for WebSocket service errors.
    Provides user-friendly error messages without exposing sensitive data.
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
