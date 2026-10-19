from flask import session
from app.token_service import TokenService

class SessionService:
    """
    Manages server-side session data.
    Tokens and sensitive data are stored in server-side sessions only.
    """
    
    @staticmethod
    def store_pkce_data(code_verifier, state):
        """Store PKCE data in session for verification during callback."""
        session['code_verifier'] = code_verifier
        session['state'] = state
    
    @staticmethod
    def get_pkce_data():
        """Retrieve and clear PKCE data from session."""
        code_verifier = session.pop('code_verifier', None)
        state = session.pop('state', None)
        return code_verifier, state
    
    @staticmethod
    def store_tokens(access_token, refresh_token=None, expires_in=None):
        """
        Store tokens in server-side session. Never expose to browser.
        
        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token (optional)
            expires_in: Token lifetime in seconds (optional)
        """
        session['access_token'] = access_token
        if refresh_token:
            session['refresh_token'] = refresh_token
        if expires_in:
            # Calculate and store the actual expiry timestamp
            session['token_expiry_time'] = TokenService.calculate_expiry_time(expires_in)
    
    @staticmethod
    def get_access_token():
        """
        Retrieve access token from session, refreshing if expired.
        
        Returns:
            str: Valid access token or None if refresh fails
        """
        access_token = session.get('access_token')
        token_expiry_time = session.get('token_expiry_time')
        refresh_token = session.get('refresh_token')
        
        # Check if token is expired
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
        """Retrieve refresh token from session."""
        return session.get('refresh_token')
    
    @staticmethod
    def get_token_expiry_time():
        """Retrieve token expiry timestamp from session."""
        return session.get('token_expiry_time')
    
    @staticmethod
    def store_selected_account(account_id, account_type=None):
        """
        Store selected account reference in session.
        
        Args:
            account_id: The account ID selected by user
            account_type: Account type (demo/real) for reference
        """
        session['selected_account_id'] = account_id
        if account_type:
            session['selected_account_type'] = account_type
    
    @staticmethod
    def get_selected_account():
        """
        Retrieve selected account from session.
        
        Returns:
            dict: Dictionary with account_id and account_type, or None
        """
        account_id = session.get('selected_account_id')
        if not account_id:
            return None
        
        return {
            'account_id': account_id,
            'account_type': session.get('selected_account_type')
        }
    
    @staticmethod
    def clear_selected_account():
        """Clear selected account from session."""
        session.pop('selected_account_id', None)
        session.pop('selected_account_type', None)
    
    @staticmethod
    def clear_session():
        """Clear all session data."""
        session.clear()
    
    @staticmethod
    def is_authenticated():
        """
        Check if user has a valid access token in session.
        
        Returns:
            bool: True if authenticated with valid token
        """
        return SessionService.get_access_token() is not None
