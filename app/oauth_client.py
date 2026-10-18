import secrets
import hashlib
import base64
from urllib.parse import urlencode
from flask import current_app

class DerivOAuthClient:
    """
    Handles Deriv OAuth 2.0 Authorization Code flow with PKCE.
    Based on: https://developers.deriv.com/llms/oauth.md
    """
    
    @staticmethod
    def generate_code_verifier():
        """Generate a cryptographically random code_verifier (43-128 characters)."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    
    @staticmethod
    def generate_code_challenge(code_verifier):
        """Generate code_challenge from code_verifier using SHA256."""
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    
    @staticmethod
    def generate_state():
        """Generate a random state for CSRF protection."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def build_authorization_url(state, code_challenge, prompt=None):
        """
        Build the authorization URL for OAuth login or signup.
        
        Args:
            state: Random string for CSRF protection
            code_challenge: BASE64URL(SHA256(code_verifier))
            prompt: Set to 'registration' for signup, None for login
            
        Returns:
            Complete authorization URL
        """
        params = {
            'response_type': 'code',
            'client_id': current_app.config['CLIENT_ID'],
            'redirect_uri': current_app.config['REDIRECT_URI'],
            'scope': current_app.config['OAUTH_SCOPES'],
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        if prompt:
            params['prompt'] = prompt
            
        return f"{current_app.config['AUTHORIZATION_ENDPOINT']}?{urlencode(params)}"
