import requests
from flask import current_app

class TokenService:
    """
    Handles OAuth token exchange and storage.
    Tokens are stored only on the server, never exposed to browser.
    """
    
    @staticmethod
    def exchange_code_for_token(code, code_verifier):
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from callback
            code_verifier: Original code_verifier used to generate code_challenge
            
        Returns:
            dict: Token response with access_token, refresh_token, etc.
            
        Raises:
            requests.exceptions.RequestException: If token exchange fails
        """
        # Mock mode for development
        if current_app.config.get('MOCK_OAUTH'):
            return {
                'access_token': 'mock_access_token_' + code_verifier[:20],
                'refresh_token': 'mock_refresh_token_' + code_verifier[:20],
                'expires_in': 3600,
                'token_type': 'Bearer',
                'scope': current_app.config['OAUTH_SCOPES']
            }
        
        # Real token exchange
        token_url = current_app.config['TOKEN_ENDPOINT']
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': current_app.config['CLIENT_ID'],
            'code': code,
            'redirect_uri': current_app.config['REDIRECT_URI'],
            'code_verifier': code_verifier
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    @staticmethod
    def refresh_access_token(refresh_token):
        """
        Use refresh token to obtain a new access token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            dict: New token response with access_token
            
        Raises:
            requests.exceptions.RequestException: If token refresh fails
        """
        token_url = current_app.config['TOKEN_ENDPOINT']
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': current_app.config['CLIENT_ID'],
            'refresh_token': refresh_token
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        
        return response.json()
