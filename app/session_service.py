from flask import session
from app.token_service import TokenService
from app.supabase_service import SupabaseService
from datetime import datetime, timedelta
import uuid

class SessionService:
    """
    Manages server-side session data with Supabase persistence.
    Combines Flask sessions (temporary) with Supabase (persistent).
    """
    
    @staticmethod
    def _get_session_id():
        """Get or create a unique session ID"""
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        return session['session_id']
    
    @staticmethod
    def _get_user_id():
        """Get user identifier from session"""
        return session.get('user_id') or session.get('selected_account_id')
    
    # ==================== PKCE Data (temporary, Flask only) ====================
    
    @staticmethod
    def store_pkce_data(code_verifier, state):
        """Store PKCE data in Flask session for verification during callback."""
        session['code_verifier'] = code_verifier
        session['state'] = state
    
    @staticmethod
    def get_pkce_data():
        """Retrieve and clear PKCE data from Flask session."""
        code_verifier = session.pop('code_verifier', None)
        state = session.pop('state', None)
        return code_verifier, state
    
    # ==================== Token Storage (Supabase + Flask) ====================
    
    @staticmethod
    def store_tokens(access_token, refresh_token=None, expires_in=None):
        """
        Store tokens in both Flask session (fast access) and Supabase (persistence).
        
        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_in: Token lifetime in seconds (optional)
        """
        # Store in Flask session for fast access
        session['access_token'] = access_token
        if refresh_token:
            session['refresh_token'] = refresh_token
        if expires_in:
            expiry_time = TokenService.calculate_expiry_time(expires_in)
            session['token_expiry_time'] = expiry_time
        
        # Also persist to Supabase
        try:
            session_id = SessionService._get_session_id()
            user_id = SessionService._get_user_id() or 'anonymous'
            
            expires_at = datetime.fromtimestamp(expiry_time) if expiry_time else datetime.utcnow() + timedelta(hours=1)
            
            SupabaseService.save_session(
                session_id=session_id,
                user_id=user_id,
                access_token=access_token,
                account_data=session.get('account_data', {}),
                expires_at=expires_at
            )
        except Exception as e:
            # Don't fail if Supabase is unavailable - Flask session still works
            from flask import current_app
            current_app.logger.warning(f'Failed to persist session to Supabase: {str(e)}')
    
    @staticmethod
    def get_access_token():
        """
        Retrieve access token from Flask session, or restore from Supabase if missing.
        Auto-refreshes if expired.
        
        Returns:
            str: Valid access token or None if refresh fails
        """
        # Try Flask session first (fast)
        access_token = session.get('access_token')
        token_expiry_time = session.get('token_expiry_time')
        
        # If not in Flask session, try Supabase (restore after page reload)
        if not access_token:
            try:
                session_id = SessionService._get_session_id()
                session_data = SupabaseService.get_session(session_id)
                
                if session_data:
                    access_token = session_data.get('access_token')
                    # Restore to Flask session
                    session['access_token'] = access_token
                    session['account_data'] = session_data.get('account_data', {})
                    session['user_id'] = session_data.get('user_id')
                    
                    # Check if token is expired
                    expires_at = session_data.get('expires_at')
                    if expires_at and isinstance(expires_at, str):
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    
                    if expires_at and expires_at < datetime.utcnow():
                        access_token = None  # Token expired
            except Exception as e:
                from flask import current_app
                current_app.logger.debug(f'Could not restore session from Supabase: {str(e)}')
        
        # Check if token is expired and refresh if needed
        refresh_token = session.get('refresh_token')
        
        if access_token and TokenService.is_token_expired(token_expiry_time):
            if refresh_token:
                try:
                    # Attempt to refresh the token
                    token_response = TokenService.refresh_access_token(refresh_token)
                    
                    # Update session with new token
                    SessionService.store_tokens(
                        access_token=token_response.get('access_token'),
                        refresh_token=token_response.get('refresh_token', refresh_token),
                        expires_in=token_response.get('expires_in')
                    )
                    
                    return token_response.get('access_token')
                except Exception:
                    # Token refresh failed, clear session
                    SessionService.clear_session()
                    return None
            else:
                # No refresh token available, clear session
                SessionService.clear_session()
                return None
        
        return access_token
    
    @staticmethod
    def get_refresh_token():
        """Retrieve refresh token from Flask session."""
        return session.get('refresh_token')
    
    @staticmethod
    def get_token_expiry_time():
        """Retrieve token expiry timestamp from Flask session."""
        return session.get('token_expiry_time')
    
    # ==================== Account Selection (Supabase + Flask) ====================
    
    @staticmethod
    def store_selected_account(account_id, account_type=None):
        """
        Store selected account in both Flask session and Supabase.
        
        Args:
            account_id: The account ID selected by user
            account_type: Account type (demo/real) for reference
        """
        session['selected_account_id'] = account_id
        if account_type:
            session['selected_account_type'] = account_type
    
    @staticmethod
    def set_selected_account(account):
        """
        Store full account object in session and persist to Supabase.
        
        Args:
            account: Account dictionary with all fields
        """
        session['selected_account'] = account
        session['selected_account_id'] = account.get('account_id')
        session['selected_account_type'] = account.get('account_type')
        session['account_data'] = account
        
        # Persist to Supabase
        try:
            session_id = SessionService._get_session_id()
            user_id = account.get('account_id') or SessionService._get_user_id()
            access_token = session.get('access_token')
            token_expiry = session.get('token_expiry_time')
            
            if access_token:
                expires_at = datetime.fromtimestamp(token_expiry) if token_expiry else datetime.utcnow() + timedelta(hours=1)
                
                SupabaseService.save_session(
                    session_id=session_id,
                    user_id=user_id,
                    access_token=access_token,
                    account_data=account,
                    expires_at=expires_at
                )
        except Exception as e:
            from flask import current_app
            current_app.logger.warning(f'Failed to persist account to Supabase: {str(e)}')
    
    @staticmethod
    def get_selected_account():
        """
        Retrieve selected account from Flask session or Supabase.
        
        Returns:
            dict: Account data or None
        """
        # Try Flask session first
        account = session.get('selected_account')
        
        # If not in Flask session, try Supabase
        if not account:
            try:
                session_id = SessionService._get_session_id()
                session_data = SupabaseService.get_session(session_id)
                
                if session_data and session_data.get('account_data'):
                    account = session_data['account_data']
                    # Restore to Flask session
                    session['selected_account'] = account
                    session['selected_account_id'] = account.get('account_id')
                    session['account_data'] = account
            except Exception as e:
                from flask import current_app
                current_app.logger.debug(f'Could not restore account from Supabase: {str(e)}')
        
        return account
    
    @staticmethod
    def clear_selected_account():
        """Clear selected account from Flask session."""
        session.pop('selected_account', None)
        session.pop('selected_account_id', None)
        session.pop('selected_account_type', None)
    
    # ==================== Session Clearing ====================
    
    @staticmethod
    def clear_session():
        """
        Clear all session data from Flask session and Supabase.
        """
        try:
            session_id = session.get('session_id')
            if session_id:
                SupabaseService.delete_session(session_id)
        except Exception:
            pass
        
        session.clear()
    
    # ==================== Session Utilities ====================
    
    @staticmethod
    def is_authenticated():
        """Check if user has valid access token."""
        return SessionService.get_access_token() is not None
    
    @staticmethod
    def has_selected_account():
        """Check if user has selected an account."""
        return SessionService.get_selected_account() is not None
