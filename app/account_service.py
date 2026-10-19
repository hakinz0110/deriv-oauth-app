import requests
from flask import current_app

class AccountService:
    """
    Handles Deriv account operations.
    Retrieves trading accounts using the authenticated REST API.
    """
    
    # Deriv API endpoint for account list
    ACCOUNTS_ENDPOINT = 'https://api.derivws.com/trading/v1/options/accounts'
    
    @staticmethod
    def get_accounts(access_token):
        """
        Retrieve all Options trading accounts for the authenticated user.
        
        Args:
            access_token: Valid OAuth access token
            
        Returns:
            list: List of account dictionaries with account_id, balance, currency, etc.
            
        Raises:
            AccountServiceError: If account retrieval fails
        """
        if not access_token:
            raise AccountServiceError('Missing access token', 'MISSING_TOKEN')
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                AccountService.ACCOUNTS_ENDPOINT,
                headers=headers,
                timeout=10
            )
            
            # Check for unsuccessful response
            if response.status_code == 401:
                raise AccountServiceError('Authentication failed - token may be invalid or expired', 'INVALID_TOKEN')
            elif response.status_code == 403:
                raise AccountServiceError('Access forbidden - insufficient permissions', 'FORBIDDEN')
            elif response.status_code == 404:
                raise AccountServiceError('Accounts endpoint not found', 'NOT_FOUND')
            elif response.status_code >= 500:
                raise AccountServiceError('Deriv API server error', 'SERVER_ERROR')
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            accounts = data.get('data', [])
            
            if not accounts:
                current_app.logger.info('No trading accounts found for user')
                return []
            
            # Log success without exposing token
            current_app.logger.info(f'Retrieved {len(accounts)} trading accounts')
            
            return accounts
            
        except requests.exceptions.Timeout:
            raise AccountServiceError('Request timeout - Deriv API did not respond', 'TIMEOUT')
        except requests.exceptions.ConnectionError:
            raise AccountServiceError('Connection error - unable to reach Deriv API', 'CONNECTION_ERROR')
        except requests.exceptions.RequestException as e:
            # Log error without exposing token
            current_app.logger.error(f'Account retrieval failed: {type(e).__name__}')
            raise AccountServiceError('Failed to retrieve accounts', 'REQUEST_FAILED')
        except ValueError as e:
            # JSON parsing error
            current_app.logger.error(f'Invalid JSON response from accounts API: {str(e)}')
            raise AccountServiceError('Invalid response from Deriv API', 'INVALID_RESPONSE')
    
    @staticmethod
    def filter_accounts_by_type(accounts, account_type):
        """
        Filter accounts by type (demo or real).
        
        Args:
            accounts: List of account dictionaries
            account_type: 'demo' or 'real'
            
        Returns:
            list: Filtered accounts
        """
        if not account_type:
            return accounts
        
        return [acc for acc in accounts if acc.get('account_type') == account_type]
    
    @staticmethod
    def filter_active_accounts(accounts):
        """
        Filter for active accounts only.
        
        Args:
            accounts: List of account dictionaries
            
        Returns:
            list: Active accounts only
        """
        return [acc for acc in accounts if acc.get('status') == 'active']
    
    @staticmethod
    def find_account_by_id(accounts, account_id):
        """
        Find a specific account by ID.
        
        Args:
            accounts: List of account dictionaries
            account_id: Account ID to find
            
        Returns:
            dict: Account dictionary or None if not found
        """
        for account in accounts:
            if account.get('account_id') == account_id:
                return account
        return None


class AccountServiceError(Exception):
    """
    Custom exception for account service errors.
    Provides user-friendly error messages without exposing sensitive data.
    """
    
    def __init__(self, message, error_code):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert error to dictionary for JSON response."""
        return {
            'error': self.error_code,
            'message': self.message
        }
