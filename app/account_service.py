import requests
from flask import current_app

class AccountService:
    """
    Handles Deriv Options trading account operations.
    Uses the new Deriv REST API for account retrieval and management.
    """
    
    # Deriv API endpoints
    LIST_ACCOUNTS_ENDPOINT = 'https://api.derivws.com/trading/v1/options/accounts'
    CREATE_ACCOUNT_ENDPOINT = 'https://api.derivws.com/trading/v1/options/accounts'
    
    @staticmethod
    def get_accounts(access_token):
        """
        Retrieve all existing Options trading accounts for authenticated user.
        
        Args:
            access_token: Valid OAuth access token
            
        Returns:
            list: List of account dictionaries with account_id, balance, currency, status, account_type
            
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
                AccountService.LIST_ACCOUNTS_ENDPOINT,
                headers=headers,
                timeout=10
            )
            
            # Check for unsuccessful response
            if response.status_code == 401:
                raise AccountServiceError('Authentication failed - token may be invalid or expired', 'INVALID_TOKEN')
            elif response.status_code == 403:
                raise AccountServiceError('Access forbidden - insufficient permissions or missing trade scope', 'FORBIDDEN')
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
            current_app.logger.error(f'Account retrieval failed: {type(e).__name__}')
            raise AccountServiceError('Failed to retrieve accounts', 'REQUEST_FAILED')
        except (ValueError, KeyError) as e:
            current_app.logger.error(f'Invalid JSON response: {str(e)}')
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
    
    @staticmethod
    def create_demo_account(access_token):
        """
        Create a new demo Options trading account.
        
        Args:
            access_token: Valid OAuth access token
            
        Returns:
            dict: Account object with account_id, balance, currency, status, account_type
            
        Raises:
            AccountServiceError: If account creation fails
        """
        if not access_token:
            raise AccountServiceError('Missing access token', 'MISSING_TOKEN')
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Create demo account with USD currency
        payload = {
            'currency': 'USD',
            'group': 'row',  # Rest of World
            'account_type': 'demo'
        }
        
        try:
            response = requests.post(
                AccountService.CREATE_ACCOUNT_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            # Check response status
            if response.status_code == 401:
                raise AccountServiceError('Authentication failed', 'INVALID_TOKEN')
            elif response.status_code == 403:
                raise AccountServiceError('Access forbidden', 'FORBIDDEN')
            elif response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get('errors', [{}])[0].get('message', 'Bad request')
                raise AccountServiceError(f'Invalid request: {error_msg}', 'BAD_REQUEST')
            elif response.status_code >= 500:
                raise AccountServiceError('Deriv API server error', 'SERVER_ERROR')
            
            response.raise_for_status()
            
            # Parse response (201 returns array, 200 returns single object)
            data = response.json()
            account_data = data.get('data')
            
            if isinstance(account_data, list):
                account = account_data[0] if account_data else None
            else:
                account = account_data
            
            if not account:
                raise AccountServiceError('No account in response', 'INVALID_RESPONSE')
            
            current_app.logger.info(f'Created demo account: {account.get("account_id")}')
            return account
            
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f'Account creation failed: {type(e).__name__}')
            raise AccountServiceError('Failed to create account', 'REQUEST_FAILED')


class AccountServiceError(Exception):
    """
    Custom exception for account service errors.
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
