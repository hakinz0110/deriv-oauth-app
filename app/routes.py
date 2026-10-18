from flask import Blueprint, redirect, request, jsonify, session
from app.oauth_client import DerivOAuthClient
from app.token_service import TokenService
from app.session_service import SessionService
import requests

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    """Health check and authentication status."""
    from flask import current_app
    
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
