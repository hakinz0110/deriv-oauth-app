from flask import session

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
        """Store tokens in server-side session. Never expose to browser."""
        session['access_token'] = access_token
        if refresh_token:
            session['refresh_token'] = refresh_token
        if expires_in:
            session['token_expires_in'] = expires_in
    
    @staticmethod
    def get_access_token():
        """Retrieve access token from session."""
        return session.get('access_token')
    
    @staticmethod
    def get_refresh_token():
        """Retrieve refresh token from session."""
        return session.get('refresh_token')
    
    @staticmethod
    def clear_session():
        """Clear all session data."""
        session.clear()
    
    @staticmethod
    def is_authenticated():
        """Check if user has a valid access token in session."""
        return 'access_token' in session
