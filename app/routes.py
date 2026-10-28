from flask import Blueprint, redirect, request, jsonify, session, render_template, current_app, g
from app.oauth_client import DerivOAuthClient
from app.token_service import TokenService
from app.session_service import SessionService
from app.account_service import AccountService, AccountServiceError
from app.websocket_service import WebSocketService, WebSocketServiceError
from app.trade_service import TradeService, TradeServiceError
from app.supabase_service import SupabaseService
from app.errors import (
    require_authentication,
    require_account_selection,
    AuthenticationError,
    NoAccountSelectedError,
    AccountNotFoundError,
    ValidationError
)
import requests

# ==================== SECURITY IMPORTS ====================
from app.security import SecurityService, require_admin
from app.validators import (
    ProposalRequestSchema, BuyContractSchema, SellContractSchema,
    BotConfigSchema, BotTradingSystemsSchema, RiskLimitsSchema,
    TradingSystemCreateSchema, TradingSystemUpdateSchema,
    AnalyticsSyncSchema, TimeframeQuerySchema, PaginationSchema,
    validate_request_data
)
# ==================== END SECURITY IMPORTS ====================

auth_bp = Blueprint('auth', __name__)

# ============================================
# ONBOARDING & AUTH ROUTES
# ============================================

@auth_bp.route('/')
def index():
    """Main page - serves first onboarding page."""
    return render_template('onboarding.html')

@auth_bp.route('/onboarding2')
def onboarding2():
    """Second onboarding page - strategy selection."""
    return render_template('onboarding2.html')

@auth_bp.route('/onboarding3')
def onboarding3():
    """Third onboarding page - protection limits."""
    return render_template('onboarding3.html')

@auth_bp.route('/login')
def login():
    """
    Login page or OAuth redirect.
    - Browser request with HTML Accept header: Shows login UI
    - Direct access or API request: Redirects to Deriv OAuth
    """
    from flask import current_app
    
    # Check if request wants HTML (browser)
    accept_header = request.headers.get('Accept', '')
    
    # If it's a browser requesting HTML, show login page
    if 'text/html' in accept_header and request.args.get('direct') != '1':
        return render_template('login.html')
    
    # Otherwise, proceed with OAuth flow
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
    Signup page or OAuth redirect with registration prompt.
    """
    from flask import current_app
    
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
        
        # Check if user has selected account
        selected_account = SessionService.get_selected_account()
        
        if not selected_account:
            # First-time login - redirect to account selection
            return redirect('/select-account')
        
        # Redirect to dashboard after successful authentication
        return redirect('/dashboard')
        
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
    return redirect('/')

# ============================================
# MAIN APP SCREENS
# ============================================

@auth_bp.route('/dashboard')
@require_authentication
def dashboard():
    """Dashboard/Home screen."""
    return render_template('dashboard.html')

@auth_bp.route('/select-account')
@require_authentication
def select_account_page():
    """Account selection page - shown on first login."""
    return render_template('select-account.html')

@auth_bp.route('/chart')
@require_authentication
def chart():
    """Chart analysis screen."""
    return render_template('chart.html')

@auth_bp.route('/trade')
@require_authentication
def trade():
    """Trade execution screen."""
    return render_template('trade.html')

@auth_bp.route('/history')
@require_authentication
def history():
    """Trade history screen."""
    return render_template('history.html')

@auth_bp.route('/settings')
@require_authentication
def settings():
    """Settings screen."""
    return render_template('settings.html')

@auth_bp.route('/trading-system')
@require_authentication
def trading_system():
    """Trading systems management screen."""
    return render_template('strategy.html')

@auth_bp.route('/bot')
@require_authentication
def bot():
    """Bot management screen."""
    return render_template('bot.html')

@auth_bp.route('/analytics')
@require_authentication
def analytics():
    """Advanced analytics and performance visualization screen."""
    return render_template('analytics.html')

# ============================================
# SUB-PAGES
# ============================================

@auth_bp.route('/profile')
@require_authentication
def profile():
    """Account profile page."""
    return render_template('profile.html')

@auth_bp.route('/risk-limits')
@require_authentication
def risk_limits():
    """Risk limits configuration page."""
    return render_template('risk-limits.html')

@auth_bp.route('/trading-system/new')
@require_authentication
def trading_system_new():
    """Create new trading system page."""
    return render_template('strategy-new.html')

@auth_bp.route('/trade/detail')
@require_authentication
def trade_detail():
    """Trade detail page."""
    return render_template('trade-detail.html')

# ============================================
# API ENDPOINTS
# ============================================

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
        
        # Store selected account in session (full object for Supabase)
        SessionService.set_selected_account(selected)
        
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




@auth_bp.route('/api/save-balance', methods=['POST'])
@require_authentication
def save_balance():
    """
    Save balance update from WebSocket to Supabase.
    Called by frontend when WebSocket receives balance update.
    
    Request Body:
        {
            "balance": 10500.50,
            "currency": "USD",
            "loginid": "DOT90004580"
        }
    
    Returns:
        JSON response with success/error
    """
    try:
        data = request.get_json()
        
        if not data or 'balance' not in data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Balance data required'
            }), 400
        
        # Get current session and account
        selected_account = SessionService.get_selected_account()
        
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        # Update account data in session with new balance
        selected_account['balance'] = data['balance']
        if 'currency' in data:
            selected_account['currency'] = data['currency']
        
        # Save updated account to session (which persists to Supabase)
        SessionService.set_selected_account(selected_account)
        
        return jsonify({
            'status': 'success',
            'message': 'Balance saved successfully'
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to save balance: {str(e)}')
        return jsonify({
            'error': 'SAVE_FAILED',
            'message': 'Failed to save balance'
        }), 500


@auth_bp.route('/api/save-trade', methods=['POST'])
@require_authentication
def save_trade():
    """
    Save trade from WebSocket to Supabase.
    
    Request Body:
        {
            "direction": "CALL",
            "symbol": "R_100",
            "contract_type": "MULTUP",
            "stake": 10.00,
            "entry_price": 1234.56,
            "contract_id": "abc123",
            ...
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Trade data required'
            }), 400
        
        # Get current account
        selected_account = SessionService.get_selected_account()
        
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        # Get user ID from session (using account_id as user_id for now)
        user_id = selected_account.get('account_id')
        
        # Save trade to Supabase
        trade_record = SupabaseService.save_trade(
            user_id=user_id,
            trade_data=data
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Trade saved successfully',
            'trade': trade_record
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to save trade: {str(e)}')
        return jsonify({
            'error': 'SAVE_FAILED',
            'message': 'Failed to save trade'
        }), 500


@auth_bp.route('/api/trades')
@require_authentication
def get_trades():
    """
    Get trade history for the current user.
    
    Query Parameters:
        limit: Maximum trades to return (default: 50)
        outcome: Filter by outcome (open, win, loss) - optional
    
    Returns:
        JSON response with trades array and statistics
    """
    try:
        # Get current account
        selected_account = SessionService.get_selected_account()
        
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        outcome = request.args.get('outcome', None, type=str)
        
        # Fetch trades from Supabase
        trades = SupabaseService.get_user_trades(user_id, limit=limit, outcome=outcome)
        
        # Calculate statistics
        total_trades = len(trades)
        wins = sum(1 for t in trades if t.get('outcome') == 'win')
        losses = sum(1 for t in trades if t.get('outcome') == 'loss')
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        net_pnl = sum(t.get('pnl', 0) for t in trades)
        
        return jsonify({
            'status': 'success',
            'trades': trades,
            'statistics': {
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': round(win_rate, 1),
                'net_pnl': round(net_pnl, 2)
            }
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to fetch trades: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch trade history'
        }), 500


@auth_bp.route('/api/proposal', methods=['POST'])
@require_authentication
def get_proposal():
    """
    Request a contract proposal (price quote).
    
    Request Body (JSON):
        {
            "contract_type": "CALL",          // Required
            "symbol": "R_100",                // Required
            "duration": 60,                   // Required (positive integer)
            "duration_unit": "s",             // Required (s/m/h/d/t)
            "amount": 10.00,                  // Required (positive number)
            "currency": "USD",                // Required
            "basis": "stake",                 // Optional (default: "stake")
            "subscribe": 1,                   // Optional (default: 1 for real-time)
            "barrier": "123.45",              // Optional (for barrier contracts)
            "barrier2": "125.00",             // Optional (for double barrier)
            "multiplier": 10                  // Optional (for multipliers)
        }
    
    Returns:
        JSON with proposal message to send via WebSocket
        
    Note:
        This endpoint validates parameters and returns a WebSocket message.
        Frontend should send this message via authenticated WebSocket connection.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Request body is required'
            }), 400
        
        # Extract required parameters
        contract_type = data.get('contract_type')
        symbol = data.get('symbol')
        duration = data.get('duration')
        duration_unit = data.get('duration_unit')
        amount = data.get('amount')
        
        # Get currency from selected account
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        currency = data.get('currency', selected_account.get('currency', 'USD'))
        
        # Optional parameters
        basis = data.get('basis', 'stake')
        subscribe = data.get('subscribe', 1)
        
        # Build kwargs for optional parameters
        kwargs = {}
        if 'barrier' in data:
            kwargs['barrier'] = data['barrier']
        if 'barrier2' in data:
            kwargs['barrier2'] = data['barrier2']
        if 'multiplier' in data:
            kwargs['multiplier'] = data['multiplier']
        if 'limit_order' in data:
            kwargs['limit_order'] = data['limit_order']
        
        # Validate and prepare proposal message
        proposal_message = TradeService.request_proposal(
            contract_type=contract_type,
            symbol=symbol,
            duration=duration,
            duration_unit=duration_unit,
            amount=amount,
            currency=currency,
            basis=basis,
            subscribe=subscribe,
            **kwargs
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Proposal request prepared',
            'proposal_message': proposal_message,
            'note': 'Send this message via authenticated WebSocket connection'
        })
        
    except TradeServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Proposal request failed: {str(e)}')
        return jsonify({
            'error': 'REQUEST_FAILED',
            'message': 'Failed to prepare proposal request'
        }), 500


@auth_bp.route('/api/proposal/forget', methods=['POST'])
@require_authentication
def forget_proposal():
    """
    Unsubscribe from a proposal stream.
    
    Request Body:
        {
            "subscription_id": "abc123"  // Required
        }
    
    Returns:
        JSON with forget message to send via WebSocket
    """
    try:
        data = request.get_json()
        
        if not data or 'subscription_id' not in data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'subscription_id is required'
            }), 400
        
        forget_message = TradeService.forget_proposal(data['subscription_id'])
        
        return jsonify({
            'status': 'success',
            'forget_message': forget_message
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Forget proposal failed: {str(e)}')
        return jsonify({
            'error': 'REQUEST_FAILED',
            'message': 'Failed to prepare forget request'
        }), 500


@auth_bp.route('/api/contracts', methods=['GET'])
@require_authentication
def get_contract_types():
    """
    Get list of supported contract types and configuration.
    
    Returns:
        JSON with supported contract types, duration units, and basis types
    """
    return jsonify({
        'status': 'success',
        'contract_types': TradeService.SUPPORTED_CONTRACT_TYPES,
        'duration_units': TradeService.DURATION_UNITS,
        'basis_types': TradeService.BASIS_TYPES,
        'contract_categories': {
            'rise_fall': ['CALL', 'PUT'],
            'higher_lower': ['CALLE', 'PUTE'],
            'matches_differs': ['DIGITMATCH', 'DIGITDIFF'],
            'even_odd': ['DIGITEVEN', 'DIGITODD'],
            'over_under': ['DIGITOVER', 'DIGITUNDER'],
            'touch': ['ONETOUCH', 'NOTOUCH'],
            'ends': ['EXPIRYMISS', 'EXPIRYRANGE'],
            'stays': ['RANGE', 'UPORDOWN'],
            'multipliers': ['MULTUP', 'MULTDOWN'],
            'accumulators': ['ACCU'],
            'asian': ['ASIANU', 'ASIAND'],
            'reset': ['RESETCALL', 'RESETPUT'],
            'tick_high_low': ['TICKHIGH', 'TICKLOW'],
            'lookbacks': ['LBFLOATCALL', 'LBFLOATPUT', 'LBHIGHLOW'],
            'runs': ['RUNHIGH', 'RUNLOW']
        }
    })


@auth_bp.route('/api/buy', methods=['POST'])
@require_authentication
def buy_contract():
    """
    Prepare buy contract message.
    
    ⚠️ CRITICAL: This endpoint prepares the buy message but does NOT execute the trade.
    Frontend MUST show confirmation dialog before sending via WebSocket.
    
    **SECURITY ENHANCED:** Rate limited (30/min), input validated, audit logged
    
    Request Body (JSON):
        {
            "proposal_id": "abc123",      // Required: From proposal response
            "price": 10.50                // Required: Maximum willing to pay (min: 0)
        }
    
    Returns:
        JSON with buy message to send via WebSocket
        
    Security:
        - Requires authentication
        - Rate limited: 30 requests per minute
        - Input validation with Marshmallow
        - Logs all buy attempts with WARNING level
        - Frontend must implement confirmation dialog
    """
    # SECURITY: Rate limiting (30 req/min for trading)
    current_app.limiter.limit("30 per minute")(lambda: None)()
    
    # SECURITY: Input validation
    validated_data, errors = validate_request_data(BuyContractSchema, request.get_json())
    if errors:
        return jsonify({'status': 'error', 'errors': errors}), 400
    
    # Get user ID for audit logging
    selected_account = SessionService.get_selected_account()
    user_id = selected_account.get('loginid') if selected_account else 'unknown'
    account_id = selected_account.get('account_id') if selected_account else 'unknown'
    
    try:
        # Prepare buy message (validation happens in service)
        buy_message = TradeService.buy_contract(
            proposal_id=validated_data['proposal_id'],
            price=validated_data['price']
        )
        
        # SECURITY: Audit log (success)
        SecurityService.log_audit(
            user_id=user_id,
            action_type='trade',
            action_subtype='buy_prepared',
            details={
                'proposal_id': validated_data['proposal_id'],
                'max_price': validated_data['price'],
                'account_id': account_id
            },
            status='success'
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Buy request prepared - REQUIRES USER CONFIRMATION',
            'buy_message': buy_message,
            'warning': '⚠️ Send this message ONLY after user confirms the trade',
            'account_id': account_id,
            'proposal_id': validated_data['proposal_id'],
            'max_price': validated_data['price']
        })
        
    except TradeServiceError as e:
        # SECURITY: Audit log (error)
        SecurityService.log_audit(
            user_id=user_id,
            action_type='trade',
            action_subtype='buy_prepared',
            details={'proposal_id': validated_data.get('proposal_id')},
            status='error',
            error_message=e.message
        )
        return jsonify(e.to_dict()), 400
    except Exception as e:
        # SECURITY: Audit log (error)
        SecurityService.log_audit(
            user_id=user_id,
            action_type='trade',
            action_subtype='buy_prepared',
            status='error',
            error_message=str(e)
        )
        current_app.logger.error(f'Buy request failed: {str(e)}')
        return jsonify({
            'error': 'REQUEST_FAILED',
            'message': 'Failed to prepare buy request'
        }), 500


@auth_bp.route('/api/sell', methods=['POST'])
@require_authentication
def sell_contract():
    """
    Prepare sell contract message.
    
    ⚠️ CRITICAL: This endpoint prepares the sell message but does NOT execute the trade.
    Frontend MUST show confirmation dialog before sending via WebSocket.
    
    **SECURITY ENHANCED:** Rate limited (30/min), input validated, audit logged
    
    Request Body (JSON):
        {
            "contract_id": 123456,        // Required: Contract to sell
            "price": 15.75                // Required: Minimum acceptable price
        }
    
    Returns:
        JSON with sell message to send via WebSocket
        
    Security:
        - Requires authentication
        - Rate limited: 30 requests per minute
        - Input validation with Marshmallow
        - Logs all sell attempts
        - Frontend must implement confirmation dialog
    """
    # SECURITY: Rate limiting (30 req/min for trading)
    current_app.limiter.limit("30 per minute")(lambda: None)()
    
    # SECURITY: Input validation
    validated_data, errors = validate_request_data(SellContractSchema, request.get_json())
    if errors:
        return jsonify({'status': 'error', 'errors': errors}), 400
    
    # Get user ID for audit logging
    selected_account = SessionService.get_selected_account()
    user_id = selected_account.get('loginid') if selected_account else 'unknown'
    
    try:
        # Prepare sell message
        sell_message = TradeService.sell_contract(
            contract_id=validated_data['contract_id'],
            price=validated_data['price']
        )
        
        # SECURITY: Audit log (success)
        SecurityService.log_audit(
            user_id=user_id,
            action_type='trade',
            action_subtype='sell_prepared',
            details={
                'contract_id': validated_data['contract_id'],
                'min_price': validated_data['price']
            },
            status='success'
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Sell request prepared - REQUIRES USER CONFIRMATION',
            'sell_message': sell_message,
            'warning': '⚠️ Send this message ONLY after user confirms the trade',
            'contract_id': validated_data['contract_id'],
            'min_price': validated_data['price']
        })
        
    except TradeServiceError as e:
        # SECURITY: Audit log (error)
        SecurityService.log_audit(
            user_id=user_id,
            action_type='trade',
            action_subtype='sell_prepared',
            details={'contract_id': validated_data.get('contract_id')},
            status='error',
            error_message=e.message
        )
        return jsonify(e.to_dict()), 400
    except Exception as e:
        # SECURITY: Audit log (error)
        SecurityService.log_audit(
            user_id=user_id,
            action_type='trade',
            action_subtype='sell_prepared',
            status='error',
            error_message=str(e)
        )
        current_app.logger.error(f'Sell request failed: {str(e)}')
        return jsonify({
            'error': 'REQUEST_FAILED',
            'message': 'Failed to prepare sell request'
        }), 500

            "price": 0                    // Optional: Minimum willing to accept (default: 0 for market)
        }
    
    Returns:
        JSON with sell message to send via WebSocket
        
    Security:
        - Requires authentication
        - Logs all sell attempts with WARNING level
        - Frontend must implement confirmation dialog
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Request body is required'
            }), 400
        
        contract_id = data.get('contract_id')
        price = data.get('price', 0)  # Default to 0 (market price)
        
        if not contract_id:
            return jsonify({
                'error': 'MISSING_CONTRACT_ID',
                'message': 'contract_id is required'
            }), 400
        
        # Prepare sell message (validation happens in service)
        sell_message = TradeService.sell_contract(
            contract_id=contract_id,
            price=price
        )
        
        # Get selected account for context
        selected_account = SessionService.get_selected_account()
        account_id = selected_account.get('account_id') if selected_account else 'unknown'
        
        return jsonify({
            'status': 'success',
            'message': 'Sell request prepared - REQUIRES USER CONFIRMATION',
            'sell_message': sell_message,
            'warning': '⚠️ Send this message ONLY after user confirms the sale',
            'account_id': account_id,
            'contract_id': contract_id,
            'min_price': price
        })
        
    except TradeServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Sell request failed: {str(e)}')
        return jsonify({
            'error': 'REQUEST_FAILED',
            'message': 'Failed to prepare sell request'
        }), 500

# ============================================
# TRADING SYSTEMS API ENDPOINTS
# ============================================

@auth_bp.route('/api/trading-systems', methods=['GET'])
@require_authentication
def get_trading_systems():
    """
    Get all trading systems for the authenticated user.
    
    Query Parameters:
        active_only: If true, returns only active systems (optional)
        entry_type: Filter by entry strategy type (optional)
        position_type: Filter by position sizing type (optional)
    
    Returns:
        JSON with user's trading systems
    """
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get query parameters
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        entry_type = request.args.get('entry_type', None)
        position_type = request.args.get('position_type', None)
        
        # Initialize service and get trading systems
        service = TradingSystemService(user_id)
        systems = service.get_user_trading_systems()
        
        # Apply filters
        if active_only:
            systems = [s for s in systems if s['is_active']]
        
        if entry_type:
            systems = [s for s in systems if s['entry_strategy_type'] == entry_type]
        
        if position_type:
            systems = [s for s in systems if s['position_sizing_type'] == position_type]
        
        return jsonify({
            'status': 'success',
            'trading_systems': systems,
            'count': len(systems)
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to get trading systems: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch trading systems'
        }), 500


@auth_bp.route('/api/trading-systems', methods=['POST'])
@require_authentication
def create_trading_system():
    """
    Create a new trading system.
    
    Request Body (JSON):
        {
            "name": "RSI Martingale System",         // Required
            "description": "RSI oversold + 2x loss", // Optional
            "contract_type": "CALL",                 // Required
            "symbol": "R_100",                       // Required
            "duration": 5,                           // Required
            "duration_unit": "t",                    // Required
            "entry_strategy_type": "rsi",            // Required
            "entry_conditions": {                    // Required
                "indicator": "rsi",
                "period": 14,
                "overbought": 70,
                "oversold": 30
            },
            "entry_logic": "AND",                    // Optional (default: "AND")
            "position_sizing_type": "martingale",    // Required
            "position_sizing_config": {              // Required
                "base_stake": 10,
                "loss_multiplier": 2,
                "max_stake": 100,
                "reset_on_win": true
            },
            "exit_strategy_type": "contract_end",    // Optional (default: "contract_end")
            "exit_conditions": {}                    // Optional
        }
    
    Returns:
        JSON with created trading system
    """
    # ==================== SECURITY: Rate Limiting ====================
    current_app.limiter.limit("30 per minute")(lambda: None)()
    # ================================================================
    
    # ==================== SECURITY: Input Validation ====================
    validated_data, errors = validate_request_data(TradingSystemCreateSchema, request.get_json())
    if errors:
        return jsonify({'status': 'error', 'errors': errors}), 400
    # ===================================================================
    
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id='unknown',
                action_type='strategy',
                action_subtype='create',
                details={'error': 'NO_ACCOUNT'},
                status='error'
            )
            # ================================================================
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Create trading system
        service = TradingSystemService(user_id)
        system = service.create_trading_system(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            contract_type=validated_data['contract_type'],
            symbol=validated_data['symbol'],
            duration=validated_data['duration'],
            duration_unit=validated_data['duration_unit'],
            entry_strategy_type=validated_data['entry_strategy_type'],
            entry_conditions=validated_data['entry_conditions'],
            entry_logic=validated_data.get('entry_logic', 'AND'),
            position_sizing_type=validated_data['position_sizing_type'],
            position_sizing_config=validated_data['position_sizing_config'],
            exit_strategy_type=validated_data.get('exit_strategy_type', 'contract_end'),
            exit_conditions=validated_data.get('exit_conditions', {})
        )
        
        # ==================== SECURITY: Audit Logging ====================
        SecurityService.log_audit(
            user_id=user_id,
            action_type='strategy',
            action_subtype='create',
            details={
                'system_id': system.get('id'),
                'name': validated_data['name'],
                'contract_type': validated_data['contract_type'],
                'symbol': validated_data['symbol'],
                'entry_strategy_type': validated_data['entry_strategy_type'],
                'position_sizing_type': validated_data['position_sizing_type']
            },
            status='success'
        )
        # ================================================================
        
        return jsonify({
            'status': 'success',
            'message': 'Trading system created successfully',
            'trading_system': system
        }), 201
        
    except ValidationError as e:
        # ==================== SECURITY: Audit Logging ====================
        SecurityService.log_audit(
            user_id=user_id if 'user_id' in locals() else 'unknown',
            action_type='strategy',
            action_subtype='create',
            details={'validation_error': str(e)},
            status='error'
        )
        # ================================================================
        return jsonify(e.to_dict()), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to create trading system: {str(e)}')
        
        # ==================== SECURITY: Audit Logging ====================
        SecurityService.log_audit(
            user_id=user_id if 'user_id' in locals() else 'unknown',
            action_type='strategy',
            action_subtype='create',
            details={'error': str(e)},
            status='error'
        )
        # ================================================================
        
        return jsonify({
            'error': 'CREATE_FAILED',
            'message': 'Failed to create trading system'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>', methods=['GET'])
@require_authentication
def get_trading_system(system_id):
    """
    Get a specific trading system by ID.
    
    Returns:
        JSON with trading system details
    """
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        service = TradingSystemService(user_id)
        system = service.get_trading_system(system_id)
        
        if not system:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Trading system not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'trading_system': system
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to get trading system: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch trading system'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>', methods=['PUT'])
@require_authentication
def update_trading_system(system_id):
    """
    Update an existing trading system.
    
    Request Body (JSON):
        {
            "name": "Updated Name",                  // Optional
            "description": "Updated desc",           // Optional
            "entry_conditions": {...},               // Optional
            "position_sizing_config": {...},         // Optional
            "exit_conditions": {...}                 // Optional
        }
    
    Returns:
        JSON with updated trading system
    """
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Request body is required'
            }), 400
        
        service = TradingSystemService(user_id)
        system = service.update_trading_system(system_id, data)
        
        if not system:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Trading system not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Trading system updated successfully',
            'trading_system': system
        })
        
    except ValidationError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to update trading system: {str(e)}')
        return jsonify({
            'error': 'UPDATE_FAILED',
            'message': 'Failed to update trading system'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>', methods=['DELETE'])
@require_authentication
def delete_trading_system(system_id):
    """
    Delete a trading system.
    
    Returns:
        JSON confirmation
    """
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        service = TradingSystemService(user_id)
        success = service.delete_trading_system(system_id)
        
        if not success:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Trading system not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Trading system deleted successfully'
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to delete trading system: {str(e)}')
        return jsonify({
            'error': 'DELETE_FAILED',
            'message': 'Failed to delete trading system'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>/activate', methods=['POST'])
@require_authentication
def activate_trading_system(system_id):
    """
    Activate a trading system.
    
    Returns:
        JSON with updated trading system
    """
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        service = TradingSystemService(user_id)
        system = service.activate_trading_system(system_id)
        
        if not system:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Trading system not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Trading system activated successfully',
            'trading_system': system
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to activate trading system: {str(e)}')
        return jsonify({
            'error': 'ACTIVATION_FAILED',
            'message': 'Failed to activate trading system'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>/deactivate', methods=['POST'])
@require_authentication
def deactivate_trading_system(system_id):
    """
    Deactivate a trading system.
    
    Returns:
        JSON with updated trading system
    """
    try:
        from app.trading_system_service import TradingSystemService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        service = TradingSystemService(user_id)
        system = service.deactivate_trading_system(system_id)
        
        if not system:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Trading system not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'message': 'Trading system deactivated successfully',
            'trading_system': system
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to deactivate trading system: {str(e)}')
        return jsonify({
            'error': 'DEACTIVATION_FAILED',
            'message': 'Failed to deactivate trading system'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>/backtest', methods=['POST'])
@require_authentication
def backtest_trading_system(system_id):
    """
    Run backtest for a trading system using historical data.
    
    Request Body (JSON):
        {
            "start_date": "2024-01-01T00:00:00Z",   // Required (ISO format)
            "end_date": "2024-12-31T23:59:59Z",     // Required (ISO format)
            "initial_balance": 10000                 // Required
        }
    
    Returns:
        JSON with backtest results and statistics
    """
    try:
        from app.trading_system_executor import TradingSystemBacktestEngine
        from datetime import datetime
        from decimal import Decimal
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Request body is required'
            }), 400
        
        # Extract required parameters
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        initial_balance = data.get('initial_balance')
        
        if not all([start_date_str, end_date_str, initial_balance]):
            return jsonify({
                'error': 'MISSING_FIELDS',
                'message': 'start_date, end_date, and initial_balance are required'
            }), 400
        
        # Parse dates
        try:
            start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({
                'error': 'INVALID_DATE',
                'message': 'Dates must be in ISO format (YYYY-MM-DDTHH:MM:SSZ)'
            }), 400
        
        # Validate date range
        if start_date >= end_date:
            return jsonify({
                'error': 'INVALID_DATE_RANGE',
                'message': 'start_date must be before end_date'
            }), 400
        
        # Run backtest
        engine = TradingSystemBacktestEngine(user_id, system_id)
        results = engine.run_backtest(
            start_date=start_date,
            end_date=end_date,
            initial_balance=Decimal(str(initial_balance))
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Backtest completed successfully',
            'results': results
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Backtest failed: {str(e)}')
        return jsonify({
            'error': 'BACKTEST_FAILED',
            'message': f'Failed to run backtest: {str(e)}'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>/backtests', methods=['GET'])
@require_authentication
def get_trading_system_backtests(system_id):
    """
    Get all backtest results for a trading system.
    
    Returns:
        JSON with backtest history
    """
    try:
        from app.supabase_service import SupabaseService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Fetch backtests from database
        supabase = SupabaseService.get_client()
        result = supabase.table('trading_system_backtests')\
            .select('*')\
            .eq('trading_system_id', system_id)\
            .eq('user_id', user_id)\
            .order('created_at', desc=True)\
            .execute()
        
        return jsonify({
            'status': 'success',
            'backtests': result.data,
            'count': len(result.data)
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to get backtests: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch backtest results'
        }), 500


@auth_bp.route('/api/trading-systems/<system_id>/execute', methods=['POST'])
@require_authentication
def execute_trading_system(system_id):
    """
    Execute a trading system with current market conditions.
    
    Request Body (JSON):
        {
            "market_data": {              // Required: Current market data
                "symbol": "R_100",
                "current_price": 1234.56,
                "tick_history": [...]     // Recent tick history for indicators
            }
        }
    
    Returns:
        JSON with execution result
    """
    try:
        from app.trading_system_executor import TradingSystemExecutor
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        data = request.get_json()
        if not data or 'market_data' not in data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'market_data is required in request body'
            }), 400
        
        market_data = data['market_data']
        
        # Execute trading system
        executor = TradingSystemExecutor(user_id, system_id)
        result = executor.execute_trade(market_data)
        
        return jsonify({
            'status': 'success',
            'result': result
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Trading system execution failed: {str(e)}')
        return jsonify({
            'error': 'EXECUTION_FAILED',
            'message': f'Failed to execute trading system: {str(e)}'
        }), 500


@auth_bp.route('/api/trading-systems/entry-types', methods=['GET'])
@require_authentication
def get_entry_strategy_types():
    """
    Get list of supported entry strategy types and their configurations.
    
    Returns:
        JSON with entry strategy types and required parameters
    """
    return jsonify({
        'status': 'success',
        'entry_types': {
            'manual': {
                'name': 'Manual Entry',
                'description': 'Manually trigger trades',
                'parameters': []
            },
            'rsi': {
                'name': 'RSI (Relative Strength Index)',
                'description': 'Enter when RSI crosses thresholds',
                'parameters': ['period', 'overbought', 'oversold']
            },
            'macd': {
                'name': 'MACD (Moving Average Convergence Divergence)',
                'description': 'Enter on MACD signal line crossovers',
                'parameters': ['fast_period', 'slow_period', 'signal_period']
            },
            'ema_cross': {
                'name': 'EMA Crossover',
                'description': 'Enter when fast EMA crosses slow EMA',
                'parameters': ['fast_period', 'slow_period']
            },
            'bb': {
                'name': 'Bollinger Bands',
                'description': 'Enter when price touches bands',
                'parameters': ['period', 'std_dev']
            },
            'sma': {
                'name': 'SMA (Simple Moving Average)',
                'description': 'Enter when price crosses SMA',
                'parameters': ['period']
            },
            'tick_analysis': {
                'name': 'Tick Analysis',
                'description': 'Pattern recognition on tick movements',
                'parameters': ['pattern_type', 'lookback_ticks']
            },
            'price_based': {
                'name': 'Price-Based',
                'description': 'Enter at specific price levels',
                'parameters': ['target_price', 'condition']
            }
        }
    })


@auth_bp.route('/api/trading-systems/position-types', methods=['GET'])
@require_authentication
def get_position_sizing_types():
    """
    Get list of supported position sizing types and their configurations.
    
    Returns:
        JSON with position sizing types and required parameters
    """
    return jsonify({
        'status': 'success',
        'position_types': {
            'fixed': {
                'name': 'Fixed Stake',
                'description': 'Same stake amount every trade',
                'parameters': ['stake_amount']
            },
            'martingale': {
                'name': 'Martingale',
                'description': 'Multiply stake after losses',
                'parameters': ['base_stake', 'loss_multiplier', 'max_stake', 'reset_on_win']
            },
            'anti_martingale': {
                'name': 'Anti-Martingale',
                'description': 'Multiply stake after wins',
                'parameters': ['base_stake', 'win_multiplier', 'max_stake', 'reset_on_loss']
            },
            'compound': {
                'name': 'Compound',
                'description': 'Stake percentage of current balance',
                'parameters': ['percentage', 'min_stake', 'max_stake']
            },
            'fibonacci': {
                'name': 'Fibonacci',
                'description': 'Follow Fibonacci sequence on losses',
                'parameters': ['base_stake', 'max_stake', 'reset_on_win']
            },
            'dalembert': {
                'name': "D'Alembert",
                'description': 'Increase stake by fixed amount on loss',
                'parameters': ['base_stake', 'increment', 'max_stake', 'reset_on_win']
            }
        }
    })


# ============================================
# BOT AUTOMATION API ENDPOINTS
# ============================================

@auth_bp.route('/api/bot', methods=['GET'])
@require_authentication
def get_bot():
    """
    Get user's bot (creates one if doesn't exist).
    Each user has exactly ONE bot.
    
    Returns:
        JSON with bot details
    """
    try:
        from app.bot_service import BotService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get or create bot
        bot = BotService.get_or_create_bot(user_id)
        
        return jsonify({
            'status': 'success',
            'bot': bot
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to get bot: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch bot'
        }), 500


@auth_bp.route('/api/bot/config', methods=['PUT'])
@require_authentication
def update_bot_config():
    """
    Update bot configuration.
    
    Request Body:
        {
            "max_concurrent_trades": 3,
            "check_interval_seconds": 5,
            "enable_notifications": true,
            "auto_restart_on_error": false
        }
    
    Returns:
        JSON with updated bot
    """
    try:
        from app.bot_service import BotService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'Request body is required'
            }), 400
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Update config
        updated_bot = BotService.update_bot_config(bot['id'], data)
        
        return jsonify({
            'status': 'success',
            'message': 'Bot configuration updated',
            'bot': updated_bot
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to update bot config: {str(e)}')
        return jsonify({
            'error': 'UPDATE_FAILED',
            'message': 'Failed to update bot configuration'
        }), 500


@auth_bp.route('/api/bot/trading-systems', methods=['PUT'])
@require_authentication
def set_bot_trading_systems():
    """
    Set which trading systems the bot should manage.
    
    Request Body:
        {
            "trading_system_ids": ["uuid1", "uuid2", ...]
        }
    
    Returns:
        JSON with updated bot
    """
    try:
        from app.bot_service import BotService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        data = request.get_json()
        if not data or 'trading_system_ids' not in data:
            return jsonify({
                'error': 'INVALID_REQUEST',
                'message': 'trading_system_ids is required'
            }), 400
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Update trading systems
        updated_bot = BotService.set_active_trading_systems(
            bot['id'],
            data['trading_system_ids']
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Trading systems updated',
            'bot': updated_bot
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to set trading systems: {str(e)}')
        return jsonify({
            'error': 'UPDATE_FAILED',
            'message': 'Failed to update trading systems'
        }), 500


@auth_bp.route('/api/bot/start', methods=['POST'])
@require_authentication
def start_bot():
    """
    Start the trading bot.
    
    Returns:
        JSON with bot status
    """
    # ==================== SECURITY: Rate Limiting ====================
    current_app.limiter.limit("10 per minute")(lambda: None)()
    # ================================================================
    
    try:
        from app.bot_service import BotService
        from app.bot_executor import BotExecutor
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id='unknown',
                action_type='bot',
                action_subtype='start',
                details={'error': 'NO_ACCOUNT'},
                status='error'
            )
            # ================================================================
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        access_token = SessionService.get_access_token()
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Check if already running
        if BotExecutor.is_bot_running(bot['id']):
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id=user_id,
                action_type='bot',
                action_subtype='start',
                details={'bot_id': bot['id'], 'error': 'BOT_ALREADY_RUNNING'},
                status='error'
            )
            # ================================================================
            return jsonify({
                'error': 'BOT_ALREADY_RUNNING',
                'message': 'Bot is already running'
            }), 400
        
        # Check if trading systems configured
        if not bot.get('active_trading_systems'):
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id=user_id,
                action_type='bot',
                action_subtype='start',
                details={'bot_id': bot['id'], 'error': 'NO_TRADING_SYSTEMS'},
                status='error'
            )
            # ================================================================
            return jsonify({
                'error': 'NO_TRADING_SYSTEMS',
                'message': 'Please configure trading systems before starting bot'
            }), 400
        
        # Start bot
        executor = BotExecutor.start_bot(
            bot_id=bot['id'],
            user_id=user_id,
            access_token=access_token,
            account_id=user_id
        )
        
        # ==================== SECURITY: Audit Logging ====================
        SecurityService.log_audit(
            user_id=user_id,
            action_type='bot',
            action_subtype='start',
            details={
                'bot_id': bot['id'],
                'trading_systems_count': len(bot.get('active_trading_systems', [])),
                'bot_status': executor.get_status()
            },
            status='success'
        )
        # ================================================================
        
        return jsonify({
            'status': 'success',
            'message': 'Bot started successfully',
            'bot_status': executor.get_status()
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to start bot: {str(e)}')
        
        # ==================== SECURITY: Audit Logging ====================
        SecurityService.log_audit(
            user_id=user_id if 'user_id' in locals() else 'unknown',
            action_type='bot',
            action_subtype='start',
            details={'error': str(e)},
            status='error'
        )
        # ================================================================
        
        return jsonify({
            'error': 'START_FAILED',
            'message': f'Failed to start bot: {str(e)}'
        }), 500


@auth_bp.route('/api/bot/stop', methods=['POST'])
@require_authentication
def stop_bot():
    """
    Stop the trading bot.
    
    Returns:
        JSON confirmation
    """
    try:
        from app.bot_service import BotService
        from app.bot_executor import BotExecutor
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Stop bot
        stopped = BotExecutor.stop_bot(bot['id'])
        
        if not stopped:
            return jsonify({
                'error': 'BOT_NOT_RUNNING',
                'message': 'Bot is not running'
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Bot stopped successfully'
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to stop bot: {str(e)}')
        return jsonify({
            'error': 'STOP_FAILED',
            'message': f'Failed to stop bot: {str(e)}'
        }), 500


@auth_bp.route('/api/bot/pause', methods=['POST'])
@require_authentication
def pause_bot():
    """
    Pause the trading bot.
    
    Returns:
        JSON confirmation
    """
    try:
        from app.bot_service import BotService
        from app.bot_executor import BotExecutor
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Get executor
        executor = BotExecutor.get_bot_executor(bot['id'])
        
        if not executor:
            return jsonify({
                'error': 'BOT_NOT_RUNNING',
                'message': 'Bot is not running'
            }), 400
        
        # Pause bot
        executor.pause()
        
        return jsonify({
            'status': 'success',
            'message': 'Bot paused successfully'
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to pause bot: {str(e)}')
        return jsonify({
            'error': 'PAUSE_FAILED',
            'message': f'Failed to pause bot: {str(e)}'
        }), 500


@auth_bp.route('/api/bot/resume', methods=['POST'])
@require_authentication
def resume_bot():
    """
    Resume the trading bot from paused state.
    
    Returns:
        JSON confirmation
    """
    try:
        from app.bot_service import BotService
        from app.bot_executor import BotExecutor
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Get executor
        executor = BotExecutor.get_bot_executor(bot['id'])
        
        if not executor:
            return jsonify({
                'error': 'BOT_NOT_RUNNING',
                'message': 'Bot is not running'
            }), 400
        
        # Resume bot
        executor.resume()
        
        return jsonify({
            'status': 'success',
            'message': 'Bot resumed successfully'
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to resume bot: {str(e)}')
        return jsonify({
            'error': 'RESUME_FAILED',
            'message': f'Failed to resume bot: {str(e)}'
        }), 500


@auth_bp.route('/api/bot/status', methods=['GET'])
@require_authentication
def get_bot_status():
    """
    Get real-time bot status.
    
    Returns:
        JSON with bot status
    """
    try:
        from app.bot_service import BotService
        from app.bot_executor import BotExecutor
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get bot from database
        bot = BotService.get_or_create_bot(user_id)
        
        # Get executor status if running
        executor = BotExecutor.get_bot_executor(bot['id'])
        executor_status = executor.get_status() if executor else None
        
        return jsonify({
            'status': 'success',
            'bot': bot,
            'executor_status': executor_status,
            'is_running': BotExecutor.is_bot_running(bot['id'])
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to get bot status: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch bot status'
        }), 500


@auth_bp.route('/api/bot/logs', methods=['GET'])
@require_authentication
def get_bot_logs():
    """
    Get bot activity logs.
    
    Query Parameters:
        limit: Maximum logs to return (default: 100)
        event_type: Filter by event type (optional)
    
    Returns:
        JSON with log entries
    """
    try:
        from app.bot_service import BotService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get bot
        bot = BotService.get_or_create_bot(user_id)
        
        # Get query parameters
        limit = request.args.get('limit', 100, type=int)
        event_type = request.args.get('event_type', None, type=str)
        
        # Get logs
        logs = BotService.get_bot_logs(bot['id'], limit=limit, event_type=event_type)
        
        return jsonify({
            'status': 'success',
            'logs': logs,
            'count': len(logs)
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'Failed to get bot logs: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch bot logs'
        }), 500


# ============================================================================
# Risk Management Endpoints
# ============================================================================

@auth_bp.route('/api/risk-limits', methods=['GET'])
@require_authentication
def get_risk_limits():
    """
    Get user risk limits.
    Returns:
        JSON with user risk limits
    """
    try:
        from app.risk_service import RiskService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get risk limits
        risk_service = RiskService(current_app.supabase)
        result = risk_service.get_risk_limits(user_id)
        
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.error(f'Failed to get risk limits: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch risk limits'
        }), 500


@auth_bp.route('/api/risk-limits', methods=['POST'])
@require_authentication
def update_risk_limits():
    """
    Update user risk limits.
    Request Body:
        JSON with risk limit values
    Returns:
        JSON with updated risk limits
    """
    # ==================== SECURITY: Rate Limiting ====================
    current_app.limiter.limit("30 per minute")(lambda: None)()
    # ================================================================
    
    # ==================== SECURITY: Input Validation ====================
    validated_data, errors = validate_request_data(RiskLimitsSchema, request.get_json())
    if errors:
        return jsonify({'status': 'error', 'errors': errors}), 400
    # ===================================================================
    
    try:
        from app.risk_service import RiskService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id='unknown',
                action_type='risk',
                action_subtype='update',
                details={'error': 'NO_ACCOUNT'},
                status='error'
            )
            # ================================================================
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Validate and save
        risk_service = RiskService(current_app.supabase)
        result = risk_service.save_risk_limits(user_id, validated_data)
        
        if result['status'] == 'success':
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id=user_id,
                action_type='risk',
                action_subtype='update',
                details={
                    'max_daily_loss': validated_data.get('max_daily_loss'),
                    'max_stake_per_trade': validated_data.get('max_stake_per_trade'),
                    'max_open_trades': validated_data.get('max_open_trades')
                },
                status='success'
            )
            # ================================================================
            return jsonify(result)
        else:
            # ==================== SECURITY: Audit Logging ====================
            SecurityService.log_audit(
                user_id=user_id,
                action_type='risk',
                action_subtype='update',
                details={'error': result.get('message')},
                status='error'
            )
            # ================================================================
            return jsonify(result), 400
            
    except Exception as e:
        current_app.logger.error(f'Failed to update risk limits: {str(e)}')
        
        # ==================== SECURITY: Audit Logging ====================
        SecurityService.log_audit(
            user_id=user_id if 'user_id' in locals() else 'unknown',
            action_type='risk',
            action_subtype='update',
            details={'error': str(e)},
            status='error'
        )
        # ================================================================
        
        return jsonify({
            'error': 'UPDATE_FAILED',
            'message': 'Failed to update risk limits'
        }), 500


@auth_bp.route('/api/risk-limits/validate', methods=['POST'])
@require_authentication
def validate_trade():
    """
    Validate a proposed trade against risk limits.
    Request Body:
        {
            "stake": Decimal,
            "balance": Decimal
        }
    Returns:
        JSON with validation result
    """
    try:
        from app.risk_service import RiskService
        from decimal import Decimal
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        data = request.get_json()
        
        stake = Decimal(str(data.get('stake', 0)))
        balance = Decimal(str(data.get('balance', 0)))
        
        # Validate trade
        risk_service = RiskService(current_app.supabase)
        result = risk_service.validate_trade_against_limits(user_id, stake, balance)
        
        return jsonify(result)
            
    except Exception as e:
        current_app.logger.error(f'Failed to validate trade: {str(e)}')
        return jsonify({
            'error': 'VALIDATION_FAILED',
            'message': 'Failed to validate trade'
        }), 500


@auth_bp.route('/api/risk-limits/check-trading', methods=['GET'])
@require_authentication
def check_trading_allowed():
    """
    Check if user is allowed to place new trades.
    Returns:
        JSON with check result
    """
    try:
        from app.risk_service import RiskService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Check if trading allowed
        risk_service = RiskService(current_app.supabase)
        allowed, reason = risk_service.is_trading_allowed(user_id)
        
        return jsonify({
            'allowed': allowed,
            'reason': reason
        })
            
    except Exception as e:
        current_app.logger.error(f'Failed to check trading allowed: {str(e)}')
        return jsonify({
            'error': 'CHECK_FAILED',
            'message': 'Failed to check trading status'
        }), 500


@auth_bp.route('/api/risk-limits/daily-loss', methods=['GET'])
@require_authentication
def check_daily_loss():
    """
    Check daily loss limit status.
    Returns:
        JSON with daily loss information
    """
    try:
        from app.risk_service import RiskService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Check daily loss
        risk_service = RiskService(current_app.supabase)
        result = risk_service.check_daily_loss_limit(user_id)
        
        return jsonify({
            'status': 'success',
            **result
        })
            
    except Exception as e:
        current_app.logger.error(f'Failed to check daily loss: {str(e)}')
        return jsonify({
            'error': 'CHECK_FAILED',
            'message': 'Failed to check daily loss limit'
        }), 500


@auth_bp.route('/api/risk-tracking', methods=['GET'])
@require_authentication
def get_risk_tracking():
    """
    Get today's risk tracking statistics.
    Returns:
        JSON with tracking statistics
    """
    try:
        from app.risk_service import RiskService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get tracking
        risk_service = RiskService(current_app.supabase)
        result = risk_service.get_daily_tracking(user_id)
        
        if result['status'] == 'success':
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        current_app.logger.error(f'Failed to get risk tracking: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch risk tracking'
        }), 500


# ============================================
# SECTION 5: ADVANCED ANALYTICS ROUTES
# ============================================

@auth_bp.route('/api/analytics/sync', methods=['POST'])
@require_authentication
def sync_trades():
    """
    Sync trade history from Deriv API profit_table to local database.
    
    Request Body (optional):
        {
            "days_back": 90,      // Number of days to sync (default 90)
            "batch_size": 500     // Records per batch (default 500, max 500)
        }
    
    Returns:
        JSON with sync results
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        access_token = session.get('access_token')
        
        if not access_token:
            return jsonify({
                'error': 'NO_TOKEN',
                'message': 'Authentication token not found'
            }), 401
        
        # Get optional parameters
        data = request.get_json() or {}
        days_back = data.get('days_back', 90)
        batch_size = data.get('batch_size', 500)
        
        # Validate parameters
        if not isinstance(days_back, int) or days_back < 1 or days_back > 365:
            return jsonify({
                'error': 'INVALID_PARAMETER',
                'message': 'days_back must be between 1 and 365'
            }), 400
        
        if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 500:
            return jsonify({
                'error': 'INVALID_PARAMETER',
                'message': 'batch_size must be between 1 and 500'
            }), 400
        
        # Sync trades
        result = AnalyticsService.sync_trades_from_deriv(
            user_id=user_id,
            access_token=access_token,
            days_back=days_back,
            batch_size=batch_size
        )
        
        return jsonify({
            'status': 'success',
            **result
        })
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to sync trades: {str(e)}')
        return jsonify({
            'error': 'SYNC_FAILED',
            'message': 'Failed to sync trades from Deriv API'
        }), 500


@auth_bp.route('/api/analytics/overview', methods=['GET'])
@require_authentication
def get_analytics_overview():
    """
    Get comprehensive analytics overview with all performance metrics.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
        symbol (optional): Filter by specific symbol
        trading_system_id (optional): Filter by trading system UUID
    
    Returns:
        JSON with win rate, profit factor, max drawdown, expectancy
    """
    # ==================== PERFORMANCE: Caching ====================
    # Cache key includes user and query params for accurate cache hits
    cache_key = f"analytics_overview_{SessionService.get_selected_account().get('account_id')}_{request.args.get('timeframe', 'all')}_{request.args.get('symbol', 'all')}_{request.args.get('trading_system_id', 'all')}"
    cached_result = current_app.cache.get(cache_key)
    if cached_result:
        return jsonify(cached_result)
    # ================================================================
    
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        # Get query parameters
        timeframe = request.args.get('timeframe', 'all')
        symbol = request.args.get('symbol')
        trading_system_id = request.args.get('trading_system_id')
        
        # Validate timeframe
        if timeframe not in ['hourly', 'daily', 'all']:
            return jsonify({
                'error': 'INVALID_PARAMETER',
                'message': 'timeframe must be hourly, daily, or all'
            }), 400
        
        # Get analytics overview
        result = AnalyticsService.get_analytics_overview(
            user_id=user_id,
            timeframe=timeframe,
            symbol=symbol,
            trading_system_id=trading_system_id
        )
        
        response_data = {
            'status': 'success',
            'data': result
        }
        
        # ==================== PERFORMANCE: Cache Result ====================
        # Cache for 30 seconds (analytics data doesn't change frequently)
        current_app.cache.set(cache_key, response_data, timeout=30)
        # ==================================================================
        
        return jsonify(response_data)
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get analytics overview: {str(e)}')
        return jsonify({
            'error': 'ANALYTICS_FAILED',
            'message': 'Failed to calculate analytics'
        }), 500


@auth_bp.route('/api/analytics/win-rate', methods=['GET'])
@require_authentication
def get_win_rate():
    """
    Get win rate analysis.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
        symbol (optional): Filter by specific symbol
        trading_system_id (optional): Filter by trading system UUID
    
    Returns:
        JSON with win rate percentage and trade counts
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        timeframe = request.args.get('timeframe', 'all')
        symbol = request.args.get('symbol')
        trading_system_id = request.args.get('trading_system_id')
        
        result = AnalyticsService.calculate_win_rate(
            user_id=user_id,
            timeframe=timeframe,
            symbol=symbol,
            trading_system_id=trading_system_id
        )
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to calculate win rate: {str(e)}')
        return jsonify({
            'error': 'CALCULATION_FAILED',
            'message': 'Failed to calculate win rate'
        }), 500


@auth_bp.route('/api/analytics/profit-factor', methods=['GET'])
@require_authentication
def get_profit_factor():
    """
    Get profit factor analysis.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
        symbol (optional): Filter by specific symbol
        trading_system_id (optional): Filter by trading system UUID
    
    Returns:
        JSON with profit factor, gross profit, gross loss, and rating
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        timeframe = request.args.get('timeframe', 'all')
        symbol = request.args.get('symbol')
        trading_system_id = request.args.get('trading_system_id')
        
        result = AnalyticsService.calculate_profit_factor(
            user_id=user_id,
            timeframe=timeframe,
            symbol=symbol,
            trading_system_id=trading_system_id
        )
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to calculate profit factor: {str(e)}')
        return jsonify({
            'error': 'CALCULATION_FAILED',
            'message': 'Failed to calculate profit factor'
        }), 500


@auth_bp.route('/api/analytics/max-drawdown', methods=['GET'])
@require_authentication
def get_max_drawdown():
    """
    Get maximum drawdown analysis.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
        symbol (optional): Filter by specific symbol
        trading_system_id (optional): Filter by trading system UUID
    
    Returns:
        JSON with max drawdown percentage, amounts, and recovery status
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        timeframe = request.args.get('timeframe', 'all')
        symbol = request.args.get('symbol')
        trading_system_id = request.args.get('trading_system_id')
        
        result = AnalyticsService.calculate_max_drawdown(
            user_id=user_id,
            timeframe=timeframe,
            symbol=symbol,
            trading_system_id=trading_system_id
        )
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to calculate max drawdown: {str(e)}')
        return jsonify({
            'error': 'CALCULATION_FAILED',
            'message': 'Failed to calculate max drawdown'
        }), 500


@auth_bp.route('/api/analytics/expectancy', methods=['GET'])
@require_authentication
def get_expectancy():
    """
    Get expectancy (expected value per trade) analysis.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
        symbol (optional): Filter by specific symbol
        trading_system_id (optional): Filter by trading system UUID
    
    Returns:
        JSON with expectancy, average win, average loss, and assessment
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        timeframe = request.args.get('timeframe', 'all')
        symbol = request.args.get('symbol')
        trading_system_id = request.args.get('trading_system_id')
        
        result = AnalyticsService.calculate_expectancy(
            user_id=user_id,
            timeframe=timeframe,
            symbol=symbol,
            trading_system_id=trading_system_id
        )
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to calculate expectancy: {str(e)}')
        return jsonify({
            'error': 'CALCULATION_FAILED',
            'message': 'Failed to calculate expectancy'
        }), 500


@auth_bp.route('/api/analytics/by-symbol', methods=['GET'])
@require_authentication
def get_analytics_by_symbol():
    """
    Get analytics breakdown by trading symbol.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
    
    Returns:
        JSON with analytics for each symbol
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        timeframe = request.args.get('timeframe', 'all')
        
        # Get all unique symbols for the user
        supabase = SupabaseService.get_client()
        symbols_result = supabase.table('trades').select('symbol').eq(
            'user_id', user_id
        ).execute()
        
        unique_symbols = list(set([t['symbol'] for t in symbols_result.data if t.get('symbol')]))
        
        # Get analytics for each symbol
        by_symbol = {}
        for symbol in unique_symbols:
            by_symbol[symbol] = AnalyticsService.get_analytics_overview(
                user_id=user_id,
                timeframe=timeframe,
                symbol=symbol
            )
        
        return jsonify({
            'status': 'success',
            'data': {
                'timeframe': timeframe,
                'symbols': by_symbol
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Failed to get analytics by symbol: {str(e)}')
        return jsonify({
            'error': 'ANALYTICS_FAILED',
            'message': 'Failed to get analytics by symbol'
        }), 500


@auth_bp.route('/api/analytics/by-strategy', methods=['GET'])
@require_authentication
def get_analytics_by_strategy():
    """
    Get analytics breakdown by trading system/strategy.
    
    Query Parameters:
        timeframe (optional): 'hourly', 'daily', 'all' (default: 'all')
    
    Returns:
        JSON with analytics for each trading system
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        timeframe = request.args.get('timeframe', 'all')
        
        # Get all unique trading systems for the user
        supabase = SupabaseService.get_client()
        systems_result = supabase.table('trades').select('trading_system_id').eq(
            'user_id', user_id
        ).execute()
        
        unique_systems = list(set([
            t['trading_system_id'] for t in systems_result.data 
            if t.get('trading_system_id')
        ]))
        
        # Get analytics for each system
        by_system = {}
        for system_id in unique_systems:
            # Get system name
            system_info = supabase.table('trading_systems').select('name').eq(
                'id', system_id
            ).single().execute()
            
            system_name = system_info.data.get('name', 'Unknown') if system_info.data else 'Unknown'
            
            by_system[system_id] = {
                'name': system_name,
                'analytics': AnalyticsService.get_analytics_overview(
                    user_id=user_id,
                    timeframe=timeframe,
                    trading_system_id=system_id
                )
            }
        
        return jsonify({
            'status': 'success',
            'data': {
                'timeframe': timeframe,
                'trading_systems': by_system
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Failed to get analytics by strategy: {str(e)}')
        return jsonify({
            'error': 'ANALYTICS_FAILED',
            'message': 'Failed to get analytics by strategy'
        }), 500


@auth_bp.route('/api/analytics/equity-curve', methods=['GET'])
@require_authentication
def get_equity_curve():
    """
    Get equity curve data for TradingView Lightweight Charts.
    
    Shows cumulative P/L over time - the institutional standard for
    visualizing account growth/decline.
    
    Query Parameters:
        timeframe: '1H', '4H', '1D', '1W', '1M', 'All' (default: '1D')
    
    Returns:
        JSON with time-series equity data
    """
    # ==================== PERFORMANCE: Caching ====================
    selected_account = SessionService.get_selected_account()
    if not selected_account:
        return jsonify({'status': 'error', 'message': 'No account selected'}), 400
    
    timeframe = request.args.get('timeframe', '1D')
    cache_key = f"equity_curve_{selected_account.get('loginid')}_{timeframe}"
    cached_result = current_app.cache.get(cache_key)
    if cached_result:
        return jsonify(cached_result)
    # ================================================================
    
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        user_id = selected_account.get('loginid')
        
        result = AnalyticsService.get_equity_curve(
            user_id=user_id,
            timeframe=timeframe
        )
        
        response_data = {
            'status': 'success',
            'data': result
        }
        
        # ==================== PERFORMANCE: Cache Result ====================
        # Cache for 60 seconds (equity curve doesn't update frequently)
        current_app.cache.set(cache_key, response_data, timeout=60)
        # ==================================================================
        
        return jsonify(response_data)
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get equity curve: {str(e)}')
        return jsonify({
            'error': 'CHART_FAILED',
            'message': 'Failed to generate equity curve'
        }), 500


@auth_bp.route('/api/analytics/daily-pnl', methods=['GET'])
@require_authentication
def get_daily_pnl():
    """
    Get daily P/L bar chart data.
    
    Shows profit/loss per day as green (profit) or red (loss) bars.
    Essential for identifying profitable vs losing days.
    
    Query Parameters:
        timeframe: '1W', '1M', '3M', 'All' (default: '1M')
    
    Returns:
        JSON with daily P/L data
    """
    # ==================== PERFORMANCE: Caching ====================
    selected_account = SessionService.get_selected_account()
    if not selected_account:
        return jsonify({'status': 'error', 'message': 'No account selected'}), 400
    
    timeframe = request.args.get('timeframe', '1M')
    cache_key = f"daily_pnl_{selected_account.get('loginid')}_{timeframe}"
    cached_result = current_app.cache.get(cache_key)
    if cached_result:
        return jsonify(cached_result)
    # ================================================================
    
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        user_id = selected_account.get('loginid')
        
        result = AnalyticsService.get_daily_pnl_chart(
            user_id=user_id,
            timeframe=timeframe
        )
        
        response_data = {
            'status': 'success',
            'data': result
        }
        
        # ==================== PERFORMANCE: Cache Result ====================
        # Cache for 60 seconds (daily P/L doesn't update frequently)
        current_app.cache.set(cache_key, response_data, timeout=60)
        # ==================================================================
        
        return jsonify(response_data)
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get daily P/L: {str(e)}')
        return jsonify({
            'error': 'CHART_FAILED',
            'message': 'Failed to generate daily P/L chart'
        }), 500


@auth_bp.route('/api/analytics/symbols', methods=['GET'])
@require_authentication
def get_symbol_performance_data():
    """
    Get performance breakdown by trading symbol.
    
    Returns sortable table data showing which symbols are most profitable.
    Critical for identifying which instruments to focus on.
    
    Query Parameters:
        timeframe: 'all', 'daily', 'hourly' (default: 'all')
    
    Returns:
        JSON with symbol performance data
    """
    # ==================== PERFORMANCE: Caching ====================
    selected_account = SessionService.get_selected_account()
    if not selected_account:
        return jsonify({'status': 'error', 'message': 'No account selected'}), 400
    
    timeframe = request.args.get('timeframe', 'all')
    cache_key = f"symbol_performance_{selected_account.get('loginid')}_{timeframe}"
    cached_result = current_app.cache.get(cache_key)
    if cached_result:
        return jsonify(cached_result)
    # ================================================================
    
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        user_id = selected_account.get('loginid')
        
        result = AnalyticsService.get_symbol_performance(
            user_id=user_id,
            timeframe=timeframe
        )
        
        response_data = {
            'status': 'success',
            'data': result
        }
        
        # ==================== PERFORMANCE: Cache Result ====================
        # Cache for 60 seconds (symbol stats don't update frequently)
        current_app.cache.set(cache_key, response_data, timeout=60)
        # ==================================================================
        
        return jsonify(response_data)
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get symbol performance: {str(e)}')
        return jsonify({
            'error': 'ANALYSIS_FAILED',
            'message': 'Failed to get symbol performance'
        }), 500


@auth_bp.route('/api/analytics/top-strategies', methods=['GET'])
@require_authentication
def get_top_strategies_data():
    """
    Get top performing trading systems (strategies).
    
    Returns leaderboard of strategies sorted by performance metrics.
    Essential for identifying which systems to allocate more capital to.
    
    Query Parameters:
        timeframe: 'all', 'daily', 'hourly' (default: 'all')
        limit: Max number of strategies to return (default: 10)
    
    Returns:
        JSON with top strategies data
    """
    try:
        from app.analytics_service import AnalyticsService, AnalyticsServiceError
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'status': 'error',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('loginid')
        timeframe = request.args.get('timeframe', 'all')
        limit = int(request.args.get('limit', 10))
        
        result = AnalyticsService.get_top_strategies(
            user_id=user_id,
            timeframe=timeframe,
            limit=limit
        )
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AnalyticsServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get top strategies: {str(e)}')
        return jsonify({
            'error': 'ANALYSIS_FAILED',
            'message': 'Failed to get top strategies'
        }), 500


@auth_bp.route('/api/bot/recent-closures', methods=['GET'])
@require_authentication
def get_recent_trade_closures():
    """
    Get recently closed trades from bot logs.
    Used by frontend to detect trade completions for real-time analytics updates.
    
    Query Parameters:
        since (optional): ISO timestamp to get closures since that time
        limit (optional): Max number of closures to return (default: 10)
    
    Returns:
        JSON with recent trade closures
    """
    try:
        from app.bot_service import BotService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        since = request.args.get('since')
        limit = request.args.get('limit', 10, type=int)
        
        # Get recent trade_closed events from bot_logs
        supabase = SupabaseService.get_client()
        
        query = supabase.table('bot_logs').select('*').eq(
            'user_id', user_id
        ).eq(
            'event_type', 'trade_closed'
        ).order('timestamp', desc=True).limit(limit)
        
        if since:
            query = query.gte('timestamp', since)
        
        result = query.execute()
        
        closures = []
        for log in result.data:
            context = log.get('context_data', {})
            closures.append({
                'contract_id': log.get('trade_id'),
                'outcome': context.get('outcome'),
                'pnl': context.get('pnl'),
                'pnl_percentage': context.get('pnl_percentage'),
                'timestamp': log.get('timestamp'),
                'trading_system_id': log.get('trading_system_id')
            })
        
        return jsonify({
            'status': 'success',
            'closures': closures,
            'count': len(closures)
        })
        
    except Exception as e:
        current_app.logger.error(f'Failed to get recent closures: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch recent trade closures'
        }), 500


# ============================================
# SECTION 6: NOTIFICATIONS ROUTES
# ============================================

@auth_bp.route('/api/notifications', methods=['GET'])
@require_authentication
def get_notifications():
    """
    Get user notifications.
    
    Query Parameters:
        limit (optional): Max notifications to return (default: 20)
        unread_only (optional): Return only unread notifications (default: false)
    
    Returns:
        JSON with notifications list
    """
    try:
        from app.notification_service import NotificationService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        limit = request.args.get('limit', 20, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        notifications = NotificationService.get_user_notifications(
            user_id=user_id,
            limit=limit,
            unread_only=unread_only
        )
        
        return jsonify({
            'status': 'success',
            'notifications': notifications,
            'count': len(notifications)
        })
        
    except Exception as e:
        current_app.logger.error(f'Failed to get notifications: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch notifications'
        }), 500


@auth_bp.route('/api/notifications/unread-count', methods=['GET'])
@require_authentication
def get_unread_count():
    """
    Get count of unread notifications.
    Optimized endpoint for polling (returns count only).
    
    Returns:
        JSON with unread count
    """
    try:
        from app.notification_service import NotificationService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        count = NotificationService.get_unread_count(user_id)
        
        return jsonify({
            'status': 'success',
            'unread_count': count
        })
        
    except Exception as e:
        current_app.logger.error(f'Failed to get unread count: {str(e)}')
        return jsonify({
            'error': 'FETCH_FAILED',
            'message': 'Failed to fetch unread count'
        }), 500


@auth_bp.route('/api/notifications/<notification_id>/read', methods=['POST'])
@require_authentication
def mark_notification_read(notification_id):
    """
    Mark a notification as read.
    
    Returns:
        JSON with success status
    """
    try:
        from app.notification_service import NotificationService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        success = NotificationService.mark_as_read(notification_id, user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Notification marked as read'
            })
        else:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Notification not found'
            }), 404
        
    except Exception as e:
        current_app.logger.error(f'Failed to mark notification as read: {str(e)}')
        return jsonify({
            'error': 'UPDATE_FAILED',
            'message': 'Failed to update notification'
        }), 500


@auth_bp.route('/api/notifications/read-all', methods=['POST'])
@require_authentication
def mark_all_notifications_read():
    """
    Mark all notifications as read for the user.
    
    Returns:
        JSON with count of notifications marked
    """
    try:
        from app.notification_service import NotificationService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        count = NotificationService.mark_all_as_read(user_id)
        
        return jsonify({
            'status': 'success',
            'message': f'{count} notification(s) marked as read',
            'count': count
        })
        
    except Exception as e:
        current_app.logger.error(f'Failed to mark all as read: {str(e)}')
        return jsonify({
            'error': 'UPDATE_FAILED',
            'message': 'Failed to mark notifications as read'
        }), 500


@auth_bp.route('/api/notifications/<notification_id>', methods=['DELETE'])
@require_authentication
def delete_notification(notification_id):
    """
    Delete a notification.
    
    Returns:
        JSON with success status
    """
    try:
        from app.notification_service import NotificationService
        
        selected_account = SessionService.get_selected_account()
        if not selected_account:
            return jsonify({
                'error': 'NO_ACCOUNT',
                'message': 'No account selected'
            }), 400
        
        user_id = selected_account.get('account_id')
        
        success = NotificationService.delete_notification(notification_id, user_id)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'Notification deleted'
            })
        else:
            return jsonify({
                'error': 'NOT_FOUND',
                'message': 'Notification not found'
            }), 404
        
    except Exception as e:
        current_app.logger.error(f'Failed to delete notification: {str(e)}')
        return jsonify({
            'error': 'DELETE_FAILED',
            'message': 'Failed to delete notification'
        }), 500


# ============================================
# ADMIN ROUTES (Requires @require_admin)
# ============================================

@auth_bp.route('/admin')
@require_authentication
@require_admin
def admin_dashboard():
    """
    Admin dashboard page (only accessible to ADMIN_EMAILS).
    
    Returns:
        HTML admin dashboard template
    """
    return render_template('admin/dashboard.html')


@auth_bp.route('/api/admin/statistics', methods=['GET'])
@require_authentication
@require_admin
def get_admin_statistics():
    """
    Get platform statistics for admin dashboard.
    
    Query Parameters:
        timeframe: '24h', '7d', '30d', 'all' (default: '24h')
    
    Returns:
        JSON with platform metrics
    """
    try:
        from app.admin_service import AdminService, AdminServiceError
        
        timeframe = request.args.get('timeframe', '24h')
        
        result = AdminService.get_platform_statistics(timeframe=timeframe)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AdminServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get admin statistics: {str(e)}')
        return jsonify({
            'error': 'ADMIN_STATS_FAILED',
            'message': 'Failed to get platform statistics'
        }), 500


@auth_bp.route('/api/admin/users', methods=['GET'])
@require_authentication
@require_admin
def get_admin_users():
    """
    Get active users list for admin dashboard.
    
    Query Parameters:
        limit: Number of users to return (default: 50)
        offset: Pagination offset (default: 0)
    
    Returns:
        JSON with user list and pagination info
    """
    try:
        from app.admin_service import AdminService, AdminServiceError
        
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        result = AdminService.get_active_users(limit=limit, offset=offset)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AdminServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get admin users: {str(e)}')
        return jsonify({
            'error': 'ADMIN_USERS_FAILED',
            'message': 'Failed to get active users'
        }), 500


@auth_bp.route('/api/admin/health', methods=['GET'])
@require_authentication
@require_admin
def get_admin_health():
    """
    Get system health metrics for admin dashboard.
    
    Returns:
        JSON with health indicators
    """
    try:
        from app.admin_service import AdminService, AdminServiceError
        
        result = AdminService.get_system_health()
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AdminServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get system health: {str(e)}')
        return jsonify({
            'error': 'ADMIN_HEALTH_FAILED',
            'message': 'Failed to get system health'
        }), 500


@auth_bp.route('/api/admin/top-performers', methods=['GET'])
@require_authentication
@require_admin
def get_admin_top_performers():
    """
    Get top performing users for admin dashboard.
    
    Query Parameters:
        limit: Number of users to return (default: 10)
    
    Returns:
        JSON with top performers list
    """
    try:
        from app.admin_service import AdminService, AdminServiceError
        
        limit = int(request.args.get('limit', 10))
        
        result = AdminService.get_top_performers(limit=limit)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AdminServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get top performers: {str(e)}')
        return jsonify({
            'error': 'ADMIN_PERFORMERS_FAILED',
            'message': 'Failed to get top performers'
        }), 500


@auth_bp.route('/api/admin/errors', methods=['GET'])
@require_authentication
@require_admin
def get_admin_errors():
    """
    Get recent error logs for admin dashboard.
    
    Query Parameters:
        limit: Number of errors to return (default: 50)
    
    Returns:
        JSON with error logs
    """
    try:
        from app.admin_service import AdminService, AdminServiceError
        
        limit = int(request.args.get('limit', 50))
        
        result = AdminService.get_recent_errors(limit=limit)
        
        return jsonify({
            'status': 'success',
            'data': result
        })
        
    except AdminServiceError as e:
        return jsonify(e.to_dict()), 400
    except Exception as e:
        current_app.logger.error(f'Failed to get error logs: {str(e)}')
        return jsonify({
            'error': 'ADMIN_ERRORS_FAILED',
            'message': 'Failed to get error logs'
        }), 500
