import os
from dotenv import load_dotenv

# Force override any existing environment variables with .env file values
load_dotenv(override=True)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    CLIENT_ID = os.environ.get('CLIENT_ID')
    REDIRECT_URI = os.environ.get('REDIRECT_URI')
    
    # Deriv OAuth endpoints from documentation
    AUTHORIZATION_ENDPOINT = 'https://auth.deriv.com/oauth2/auth'
    TOKEN_ENDPOINT = 'https://auth.deriv.com/oauth2/token'
    
    # OAuth scopes - request all needed scopes at authorization time
    OAUTH_SCOPES = 'trade account_manage payment application_read'
    
    # Mock mode for development when OAuth is blocked
    MOCK_OAUTH = os.environ.get('MOCK_OAUTH', 'False').lower() == 'true'
    
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required")
    if not CLIENT_ID:
        raise ValueError("CLIENT_ID environment variable is required")
    if not REDIRECT_URI:
        raise ValueError("REDIRECT_URI environment variable is required")
