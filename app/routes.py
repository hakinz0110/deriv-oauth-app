from flask import Blueprint, redirect, request, jsonify, session
from app.oauth_client import DerivOAuthClient
from app.token_service import TokenService
from app.session_service import SessionService
from app.account_service import AccountService, AccountServiceError
from app.websocket_service import WebSocketService, WebSocketServiceError
from app.errors import (
    require_authentication,
    require_account_selection,
    AuthenticationError,
    NoAccountSelectedError,
    AccountNotFoundError,
    ValidationError
)
import requests

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    """Main page - serves onboarding UI or returns JSON based on Accept header."""
    from flask import current_app, render_template
    
    # Check if request is from browser (HTML) or API client (JSON)
    accept_header = request.headers.get('Accept', '')
    
    if 'text/html' in accept_header:
        # Serve HTML page
        return render_template('index.html')
    
    # Return JSON for API clients
    mock_mode = current_app.config.get('MOCK_OAUTH', False)
    
    if SessionService.is_authenticated():
        return jsonify({
            'status': 'authenticated',
            'message': 'User is authenticated',
            'mock_mode': mock_mode,
            'access_token_preview': SessionService.get_access_token()[:30] + '...' if SessionService.get_access_token() else None
        })
    return jsonify({
        'status': 'unauthenticated',
        'message': 'User is not authenticated',
        'login_url': '/login',
        'signup_url': '/signup',
        'mock_mode': mock_mode,
        'note': 'Mock mode enabled - OAuth flow simulated for development' if mock_mode else 'Real OAuth mode'
    })

@auth_bp.route('/login')
def login():
    """
    Initiate OAuth login flow.
    Redirects user to Deriv authorization endpoint.
    """
    from flask import current_app
    
    # Mock mode for development when OAuth is blocked
    if current_app.config.get('MOCK_OAUTH'):
        # Generate mock authorization code
        mock_code = 'mock_auth_code_' + DerivOAuthClient.generate_state()
        mock_state = DerivOAuthClient.generate_state()
        
        # Store mock state
        SessionService.store_pkce_data('mock_verifier', mock_state)
        
        # Redirect directly to callback with mock code
        return redirect(f"/callback?code={mock_code}&state={mock_state}")
    
    # Real OAuth flow
    code_verifier = DerivOAuthClient.generate_code_verifier()
    code_challenge = DerivOAuthClient.generate_code_challenge(code_verifier)
    state = DerivOAuthClient.generate_state()
    
    # Store PKCE data in session for verification during callback
    SessionService.store_pkce_data(code_verifier, state)
    
    # Build authorization URL
    auth_url = DerivOAuthClient.build_authorization_url(state, code_challenge)
    
    # Log the URL for debugging
    print(f"\n{'='*80}")
    print(f"GENERATED OAUTH URL:")
    print(f"{auth_url}")
    print(f"{'='*80}\n")
    
    return redirect(auth_url)

@auth_bp.route('/signup')
def signup():
    """
    Initiate OAuth signup flow.
    Redirects user to Deriv registration form.
    """
    # Generate PKCE parameters
    code_verifier = DerivOAuthClient.generate_code_verifier()
    code_challenge = DerivOAuthClient.generate_code_challenge(code_verifier)
    state = DerivOAuthClient.generate_state()
    
    # Store PKCE data in session for verification during callback
    SessionService.store_pkce_data(code_verifier, state)
    
    # Build authorization URL with prompt=registration
    auth_url = DerivOAuthClient.build_authorization_url(
        state, 
        code_challenge, 
        prompt='registration'
    )
    
    return redirect(auth_url)

@auth_bp.route('/callback')
def callback():
    """
    OAuth callback handler.
    Exchanges authorization code for access token.
    """
    # Check for error in callback
    error = request.args.get('error')
    if error:
        error_description = request.args.get('error_description', 'Unknown error')
        return jsonify({
            'error': error,
            'error_description': error_description
        }), 400
    
    # Get authorization code and state
    code = request.args.get('code')
    returned_state = request.args.get('state')
    
    if not code or not returned_state:
        return jsonify({'error': 'Missing code or state parameter'}), 400
    
    # Retrieve stored PKCE data
    code_verifier, stored_state = SessionService.get_pkce_data()
    
    if not code_verifier or not stored_state:
        return jsonify({'error': 'Session expired or invalid'}), 400
    
    # Verify state for CSRF protection
    if returned_state != stored_state:
        return jsonify({'error': 'State mismatch - possible CSRF attack'}), 400
    
    try:
        # Exchange code for tokens
        token_response = TokenService.exchange_code_for_token(code, code_verifier)
        
        # Store tokens in server-side session
        SessionService.store_tokens(
            access_token=token_response.get('access_token'),
            refresh_token=token_response.get('refresh_token'),
            expires_in=token_response.get('expires_in')
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Authentication successful'
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            'error': 'Token exchange failed',
            'details': str(e)
        }), 500

@auth_bp.route('/logout')
def logout():
    """
    Clear session and log out user.
    Clears tokens and selected account.
    """
    SessionService.clear_session()
    return jsonify({
        'status': 'success',
        'message': 'Logged out successfully'
    })

@auth_bp.route('/health')
def health():
    """Application health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Deriv OAuth Server'
    })

@auth_bp.route('/test-url')
def test_url():
    """Generate and display OAuth URL without redirecting."""
    from flask import current_app
    
    code_verifier = DerivOAuthClient.generate_code_verifier()
    code_challenge = DerivOAuthClient.generate_code_challenge(code_verifier)
    state = DerivOAuthClient.generate_state()
    
    auth_url = DerivOAuthClient.build_authorization_url(state, code_challenge)
    
    return jsonify({
        'auth_url': auth_url,
        'client_id': current_app.config['CLIENT_ID'],
        'redirect_uri': current_app.config['REDIRECT_URI'],
        'scopes': current_app.config['OAUTH_SCOPES'],
        'code_challenge': code_challenge,
        'state': state,
        'message': 'Copy the auth_url and paste it in your browser',
        'troubleshooting': {
            'if_access_denied': 'Try mobile hotspot, wait 2-3 hours, or contact Deriv support',
            'support_info': 'Provide Ray ID from error page and Client ID: ' + current_app.config['CLIENT_ID']
        }
    })


@auth_bp.route('/accounts')
@require_authentication
def get_accounts():
    """
    Retrieve all available Deriv trading accounts for the authenticated user.
    
    Returns:
        JSON response with list of accounts or error
    """
    try:
        access_token = SessionService.get_access_token()
        
        if not access_token:
            raise AuthenticationError('Access token not available')
        
        # Retrieve accounts from Deriv API
        accounts = AccountService.get_accounts(access_token)
        
        # Get currently selected account if any
        selected_account = SessionService.get_selected_account()
        
        return jsonify({
            'status': 'success',
            'accounts': accounts,
            'selected_account': selected_account,
            'count': len(accounts)
        })
        
    except AccountServiceError as e:
        return jsonify(e.to_dict()), 500
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Account retrieval error: {type(e).__name__}')
        return jsonify({
            'error': 'ACCOUNT_RETRIEVAL_FAILED',
            'message': 'Failed to retrieve accounts'
        }), 500


@auth_bp.route('/accounts/demo')
@require_authentication
def get_demo_accounts():
    """
    Retrieve demo trading accounts only.
    
    Returns:
        JSON response with list of demo accounts
    """
    try:
        access_token = SessionService.get_access_token()
        
        if not access_token:
            raise AuthenticationError('Access token not available')
        
        # Retrieve all accounts
        accounts = AccountService.get_accounts(access_token)
        
        # Filter for demo accounts only
        demo_accounts = AccountService.filter_accounts_by_type(accounts, 'demo')
        
        return jsonify({
            'status': 'success',
            'accounts': demo_accounts,
            'count': len(demo_accounts)
        })
        
    except AccountServiceError as e:
        return jsonify(e.to_dict()), 500


@auth_bp.route('/accounts/real')
@require_authentication
def get_real_accounts():
    """
    Retrieve real trading accounts only.
    
    Returns:
        JSON response with list of real accounts
    """
    try:
        access_token = SessionService.get_access_token()
        
        if not access_token:
            raise AuthenticationError('Access token not available')
        
        # Retrieve all accounts
        accounts = AccountService.get_accounts(access_token)
        
        # Filter for real accounts only
        real_accounts = AccountService.filter_accounts_by_type(accounts, 'real')
        
        return jsonify({
            'status': 'success',
            'accounts': real_accounts,
            'count': len(real_accounts)
        })
        
    except AccountServiceError as e:
        return jsonify(e.to_dict()), 500


@auth_bp.route('/accounts/select', methods=['POST'])
@require_authentication
def select_account():
    """
    Select a trading account for subsequent operations.
    
    Expected JSON body:
        {
            "account_id": "CR123456"
        }
    
    Returns:
        JSON response confirming selection or error
    """
    try:
        data = request.get_json()
        
        if not data or 'account_id' not in data:
            raise ValidationError('Missing account_id in request body')
        
        account_id = data['account_id']
        
        if not account_id or not isinstance(account_id, str):
            raise ValidationError('Invalid account_id format')
        
        # Verify the account exists and user has access
        access_token = SessionService.get_access_token()
        accounts = AccountService.get_accounts(access_token)
        
        selected = AccountService.find_account_by_id(accounts, account_id)
        
        if not selected:
            raise AccountNotFoundError(f'Account {account_id} not found or not accessible')
        
        # Store selected account in session
        SessionService.store_selected_account(
            account_id=selected['account_id'],
            account_type=selected.get('account_type')
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Account selected successfully',
            'selected_account': {
                'account_id': selected['account_id'],
                'account_type': selected.get('account_type'),
                'currency': selected.get('currency'),
                'balance': selected.get('balance')
            }
        })
        
    except AccountServiceError as e:
        return jsonify(e.to_dict()), 500
    except (ValidationError, AccountNotFoundError) as e:
        return jsonify(e.to_dict()), e.status_code


@auth_bp.route('/accounts/selected')
@require_authentication
def get_selected_account():
    """
    Get the currently selected trading account.
    
    Returns:
        JSON response with selected account or error
    """
    selected_account = SessionService.get_selected_account()
    
    if not selected_account:
        raise NoAccountSelectedError('No trading account has been selected')
    
    return jsonify({
        'status': 'success',
        'selected_account': selected_account
    })


@auth_bp.route('/accounts/clear', methods=['POST'])
@require_authentication
def clear_selected_account():
    """
    Clear the currently selected account.
    
    Returns:
        JSON response confirming clearance
    """
    SessionService.clear_selected_account()
    
    return jsonify({
        'status': 'success',
        'message': 'Selected account cleared'
    })


@auth_bp.route('/websocket/url')
@require_authentication
@require_account_selection
def get_websocket_url():
    """
    Request an authenticated WebSocket URL for the selected account.
    
    Returns:
        JSON response with WebSocket URL or error
        
    Note:
        The URL contains an embedded OTP and should not be logged or stored.
        It should be used immediately to establish a WebSocket connection.
    """
    try:
        access_token = SessionService.get_access_token()
        selected_account = SessionService.get_selected_account()
        
        if not access_token:
            raise AuthenticationError('Access token not available')
        
        account_id = selected_account['account_id']
        
        # Request OTP-authenticated WebSocket URL
        ws_url = WebSocketService.request_websocket_url(account_id, access_token)
        
        return jsonify({
            'status': 'success',
            'message': 'WebSocket URL obtained successfully',
            'account_id': account_id,
            'account_type': selected_account.get('account_type'),
            'websocket_url': ws_url,
            'note': 'Use this URL immediately to establish WebSocket connection. Do not log or store it.'
        })
        
    except WebSocketServiceError as e:
        return jsonify(e.to_dict()), 500
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'WebSocket URL request error: {type(e).__name__}')
        return jsonify({
            'error': 'WEBSOCKET_URL_FAILED',
            'message': 'Failed to obtain WebSocket URL'
        }), 500


@auth_bp.route('/market-data/url')
def get_market_data_url():
    """
    Get the public market data WebSocket URL.
    No authentication required.
    
    Returns:
        JSON response with public WebSocket URL
    """
    from app.market_data_service import MarketDataService
    
    return jsonify({
        'status': 'success',
        'message': 'Public market data WebSocket endpoint',
        'websocket_url': MarketDataService.PUBLIC_WS_URL,
        'authentication': 'none',
        'note': 'Connect directly to this URL for public market data'
    })
