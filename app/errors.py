"""
Centralized error handling for the Deriv API Flask application.
Provides user-friendly error messages without exposing sensitive data.
"""

from flask import jsonify, current_app


class AppError(Exception):
    """
    Base application error class.
    All custom errors should inherit from this class.
    """
    
    def __init__(self, message, error_code, status_code=400):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert error to dictionary for JSON response."""
        return {
            'error': self.error_code,
            'message': self.message
        }
    
    def to_response(self):
        """Convert error to Flask JSON response."""
        return jsonify(self.to_dict()), self.status_code


class AuthenticationError(AppError):
    """Error for authentication failures."""
    
    def __init__(self, message='Authentication required'):
        super().__init__(
            message=message,
            error_code='AUTHENTICATION_REQUIRED',
            status_code=401
        )


class TokenExpiredError(AppError):
    """Error for expired access tokens."""
    
    def __init__(self, message='Access token has expired'):
        super().__init__(
            message=message,
            error_code='TOKEN_EXPIRED',
            status_code=401
        )


class InvalidTokenError(AppError):
    """Error for invalid or malformed tokens."""
    
    def __init__(self, message='Invalid or malformed access token'):
        super().__init__(
            message=message,
            error_code='INVALID_TOKEN',
            status_code=401
        )


class NoAccountSelectedError(AppError):
    """Error when no account has been selected."""
    
    def __init__(self, message='No trading account selected'):
        super().__init__(
            message=message,
            error_code='NO_ACCOUNT_SELECTED',
            status_code=400
        )


class AccountNotFoundError(AppError):
    """Error when requested account is not found."""
    
    def __init__(self, message='Trading account not found'):
        super().__init__(
            message=message,
            error_code='ACCOUNT_NOT_FOUND',
            status_code=404
        )


class AccountRetrievalError(AppError):
    """Error when account retrieval fails."""
    
    def __init__(self, message='Failed to retrieve trading accounts'):
        super().__init__(
            message=message,
            error_code='ACCOUNT_RETRIEVAL_FAILED',
            status_code=500
        )


class OTPRequestError(AppError):
    """Error when OTP request for WebSocket fails."""
    
    def __init__(self, message='Failed to obtain WebSocket connection URL'):
        super().__init__(
            message=message,
            error_code='OTP_REQUEST_FAILED',
            status_code=500
        )


class WebSocketConnectionError(AppError):
    """Error when WebSocket connection fails."""
    
    def __init__(self, message='WebSocket connection failed'):
        super().__init__(
            message=message,
            error_code='WEBSOCKET_CONNECTION_FAILED',
            status_code=500
        )


class InvalidAPIResponseError(AppError):
    """Error when API returns invalid or unexpected response."""
    
    def __init__(self, message='Invalid response from Deriv API'):
        super().__init__(
            message=message,
            error_code='INVALID_API_RESPONSE',
            status_code=502
        )


class APITimeoutError(AppError):
    """Error when API request times out."""
    
    def __init__(self, message='API request timed out'):
        super().__init__(
            message=message,
            error_code='API_TIMEOUT',
            status_code=504
        )


class InsufficientPermissionsError(AppError):
    """Error when user lacks required permissions."""
    
    def __init__(self, message='Insufficient permissions for this operation'):
        super().__init__(
            message=message,
            error_code='INSUFFICIENT_PERMISSIONS',
            status_code=403
        )


class ValidationError(AppError):
    """Error for request validation failures."""
    
    def __init__(self, message='Invalid request parameters'):
        super().__init__(
            message=message,
            error_code='VALIDATION_ERROR',
            status_code=400
        )


def register_error_handlers(app):
    """
    Register error handlers with the Flask application.
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        """Handle all custom application errors."""
        current_app.logger.error(f'{error.error_code}: {error.message}')
        return error.to_response()
    
    @app.errorhandler(404)
    def handle_not_found(error):
        """Handle 404 Not Found errors."""
        return jsonify({
            'error': 'NOT_FOUND',
            'message': 'The requested resource was not found'
        }), 404
    
    @app.errorhandler(500)
    def handle_internal_error(error):
        """Handle 500 Internal Server Error."""
        current_app.logger.error(f'Internal server error: {str(error)}')
        return jsonify({
            'error': 'INTERNAL_SERVER_ERROR',
            'message': 'An internal server error occurred'
        }), 500
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle all unexpected errors."""
        current_app.logger.error(f'Unexpected error: {type(error).__name__} - {str(error)}')
        return jsonify({
            'error': 'UNEXPECTED_ERROR',
            'message': 'An unexpected error occurred'
        }), 500


def require_authentication(func):
    """
    Decorator to require authentication for route handlers.
    
    Usage:
        @auth_bp.route('/protected')
        @require_authentication
        def protected_route():
            return jsonify({'message': 'Access granted'})
    """
    from functools import wraps
    from app.session_service import SessionService
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not SessionService.is_authenticated():
            raise AuthenticationError('Please log in to access this resource')
        return func(*args, **kwargs)
    
    return wrapper


def require_account_selection(func):
    """
    Decorator to require account selection for route handlers.
    
    Usage:
        @auth_bp.route('/trade')
        @require_authentication
        @require_account_selection
        def trade_route():
            return jsonify({'message': 'Ready to trade'})
    """
    from functools import wraps
    from app.session_service import SessionService
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not SessionService.get_selected_account():
            raise NoAccountSelectedError('Please select a trading account first')
        return func(*args, **kwargs)
    
    return wrapper
