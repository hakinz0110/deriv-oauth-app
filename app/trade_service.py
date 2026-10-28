from flask import current_app
import json

class TradeService:
    """
    Trading operations service for Deriv API.
    Handles proposal requests, contract buying/selling, and portfolio management.
    
    IMPORTANT: Trading Safety Rules
    - ALL trades require explicit user confirmation
    - Do NOT automatically place trades
    - Validate all parameters before sending
    - Handle errors gracefully
    """
    
    # Supported contract types (comprehensive list)
    SUPPORTED_CONTRACT_TYPES = [
        # Rise/Fall
        'CALL', 'PUT',
        # Higher/Lower
        'CALLE', 'PUTE',
        # Matches/Differs
        'DIGITMATCH', 'DIGITDIFF',
        # Even/Odd
        'DIGITEVEN', 'DIGITODD',
        # Over/Under
        'DIGITOVER', 'DIGITUNDER',
        # Touch/No Touch
        'ONETOUCH', 'NOTOUCH',
        # Ends In/Out
        'EXPIRYMISS', 'EXPIRYRANGE',
        # Stays Between/Goes Outside
        'RANGE', 'UPORDOWN',
        # Multipliers
        'MULTUP', 'MULTDOWN',
        # Accumulators
        'ACCU',
        # Asian
        'ASIANU', 'ASIAND',
        # Reset Call/Put
        'RESETCALL', 'RESETPUT',
        # Tick High/Low
        'TICKHIGH', 'TICKLOW',
        # Lookbacks
        'LBFLOATCALL', 'LBFLOATPUT', 'LBHIGHLOW',
        # Runs
        'RUNHIGH', 'RUNLOW'
    ]
    
    # Supported duration units
    DURATION_UNITS = ['s', 'm', 'h', 'd', 't']
    
    # Basis types
    BASIS_TYPES = ['stake', 'payout']
    
    @staticmethod
    def validate_proposal_params(contract_type, symbol, duration, duration_unit, amount, currency, basis):
        """
        Validate proposal parameters before sending to API.
        
        Args:
            contract_type: Contract type to validate
            symbol: Trading symbol
            duration: Duration value
            duration_unit: Duration unit
            amount: Trade amount
            currency: Currency code
            basis: Basis type
            
        Raises:
            TradeServiceError: If validation fails
        """
        # Validate contract type
        if not contract_type or contract_type not in TradeService.SUPPORTED_CONTRACT_TYPES:
            raise TradeServiceError(
                f'Invalid contract type: {contract_type}. Must be one of: {", ".join(TradeService.SUPPORTED_CONTRACT_TYPES[:10])}...',
                'INVALID_CONTRACT_TYPE'
            )
        
        # Validate symbol
        if not symbol or not isinstance(symbol, str):
            raise TradeServiceError('Symbol is required and must be a string', 'INVALID_SYMBOL')
        
        # Validate duration
        if not isinstance(duration, (int, float)) or duration <= 0:
            raise TradeServiceError('Duration must be a positive number', 'INVALID_DURATION')
        
        # Validate duration unit
        if duration_unit not in TradeService.DURATION_UNITS:
            raise TradeServiceError(
                f'Invalid duration unit: {duration_unit}. Must be one of: {", ".join(TradeService.DURATION_UNITS)}',
                'INVALID_DURATION_UNIT'
            )
        
        # Validate amount
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise TradeServiceError('Amount must be a positive number', 'INVALID_AMOUNT')
        
        # Validate currency
        if not currency or not isinstance(currency, str):
            raise TradeServiceError('Currency is required and must be a string', 'INVALID_CURRENCY')
        
        # Validate basis
        if basis not in TradeService.BASIS_TYPES:
            raise TradeServiceError(
                f'Invalid basis: {basis}. Must be "stake" or "payout"',
                'INVALID_BASIS'
            )
    
    @staticmethod
    def request_proposal(contract_type, symbol, duration, duration_unit, amount, currency, basis='stake', subscribe=1, **kwargs):
        """
        Request a contract proposal (quote) for a trade.
        Returns the message to be sent via WebSocket (does not send directly).
        
        Best Practice: Uses subscription mode for real-time price updates.
        
        Args:
            contract_type: Type of contract (see SUPPORTED_CONTRACT_TYPES)
            symbol: Trading symbol (underlying_symbol in new API)
            duration: Duration value (positive integer)
            duration_unit: Duration unit ('s', 'm', 'h', 'd', 't')
            amount: Stake or payout amount (positive number)
            currency: Account currency (e.g., 'USD')
            basis: 'stake' or 'payout' (default: 'stake')
            subscribe: 1 for real-time updates, 0 for one-time quote (default: 1)
            **kwargs: Additional optional parameters (barrier, barrier2, multiplier, etc.)
            
        Returns:
            dict: Proposal message ready to send via WebSocket
            
        Raises:
            TradeServiceError: If parameters are invalid
            
        Example:
            msg = TradeService.request_proposal(
                contract_type='CALL',
                symbol='R_100',
                duration=60,
                duration_unit='s',
                amount=10.00,
                currency='USD'
            )
            ws.send(json.dumps(msg))
        """
        # Validate all parameters
        TradeService.validate_proposal_params(
            contract_type, symbol, duration, duration_unit, amount, currency, basis
        )
        
        # Build proposal message (NEW API format uses 'underlying_symbol')
        proposal_message = {
            'proposal': 1,
            'amount': float(amount),
            'basis': basis,
            'contract_type': contract_type,
            'currency': currency,
            'duration': int(duration),
            'duration_unit': duration_unit,
            'underlying_symbol': symbol,  # NEW API: 'underlying_symbol' not 'symbol'
            'subscribe': subscribe
        }
        
        # Add optional parameters if provided
        if 'barrier' in kwargs:
            proposal_message['barrier'] = kwargs['barrier']
        if 'barrier2' in kwargs:
            proposal_message['barrier2'] = kwargs['barrier2']
        if 'multiplier' in kwargs:
            proposal_message['multiplier'] = kwargs['multiplier']
        if 'limit_order' in kwargs:
            proposal_message['limit_order'] = kwargs['limit_order']
        
        current_app.logger.info(
            f'Prepared proposal request: {contract_type} on {symbol}, '
            f'{amount} {currency} for {duration}{duration_unit}'
        )
        
        return proposal_message
    
    @staticmethod
    def parse_proposal_response(response_data):
        """
        Parse proposal response from Deriv API.
        Handles both number and string types for prices (NEW API compatibility).
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed proposal data with standardized types
            
        Raises:
            TradeServiceError: If response is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown proposal error'),
                error.get('code', 'PROPOSAL_ERROR')
            )
        
        if 'proposal' not in response_data:
            raise TradeServiceError('Invalid proposal response: missing proposal object', 'INVALID_RESPONSE')
        
        proposal = response_data['proposal']
        
        # NEW API: Only 'id' is required, other fields may be optional
        if 'id' not in proposal:
            raise TradeServiceError('Invalid proposal response: missing proposal ID', 'INVALID_RESPONSE')
        
        # Parse and standardize fields (handle both string and number types)
        parsed = {
            'proposal_id': proposal['id'],
            'ask_price': float(proposal.get('ask_price', 0)) if proposal.get('ask_price') else None,
            'payout': float(proposal.get('payout', 0)) if proposal.get('payout') else None,
            'spot': float(proposal.get('spot', 0)) if proposal.get('spot') else None,
            'spot_time': proposal.get('spot_time'),
            'commission': float(proposal.get('commission', 0)) if proposal.get('commission') else None,
            'date_start': proposal.get('date_start'),
            'display_value': proposal.get('display_value'),
            'currency': response_data.get('currency'),
            'subscription': response_data.get('subscription')
        }
        
        current_app.logger.debug(f'Parsed proposal: ID={parsed["proposal_id"]}, Price={parsed["ask_price"]}')
        
        return parsed
    
    @staticmethod
    def forget_proposal(subscription_id):
        """
        Unsubscribe from a proposal stream.
        
        Args:
            subscription_id: Subscription ID from proposal response
            
        Returns:
            dict: Forget message to send via WebSocket
        """
        return {
            'forget': subscription_id
        }
    
    @staticmethod
    def forget_all_proposals(proposal_type='proposal'):
        """
        Unsubscribe from all proposal streams.
        
        Args:
            proposal_type: Type of proposals to forget (default: 'proposal')
            
        Returns:
            dict: Forget all message to send via WebSocket
        """
        return {
            'forget_all': proposal_type
        }
    
    @staticmethod
    def buy_contract(proposal_id, price):
        """
        Buy a contract based on a proposal.
        Returns WebSocket message to be sent (does NOT execute trade).
        
        ⚠️ CRITICAL: This method only prepares the message. 
        The caller MUST obtain user confirmation before sending.
        
        Args:
            proposal_id: Proposal ID from request_proposal response (required)
            price: Maximum price willing to pay (required, minimum: 0)
            
        Returns:
            dict: Buy message ready to send via WebSocket
            
        Raises:
            TradeServiceError: If parameters are invalid
            
        Example:
            # 1. Get user confirmation first
            if user_confirms:
                msg = TradeService.buy_contract(proposal_id='abc123', price=10.50)
                ws.send(json.dumps(msg))
        """
        # Validate proposal ID
        if not proposal_id:
            raise TradeServiceError('Proposal ID is required', 'MISSING_PROPOSAL_ID')
        
        # Validate price (NEW API: minimum 0)
        if not isinstance(price, (int, float)) or price < 0:
            raise TradeServiceError('Price must be a non-negative number', 'INVALID_PRICE')
        
        # Build buy message (NEW API format - no loginid parameter)
        buy_message = {
            'buy': proposal_id,
            'price': float(price)
        }
        
        current_app.logger.warning(
            f'⚠️ TRADE PREPARED: Buy contract proposal {proposal_id} at ${price:.2f} '
            f'- REQUIRES USER CONFIRMATION'
        )
        
        return buy_message
    
    @staticmethod
    def parse_buy_response(response_data):
        """
        Parse buy response from Deriv API.
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed buy data
            
        Raises:
            TradeServiceError: If response contains error or is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown buy error'),
                error.get('code', 'BUY_ERROR')
            )
        
        if 'buy' not in response_data:
            raise TradeServiceError('Invalid buy response: missing buy object', 'INVALID_RESPONSE')
        
        buy_data = response_data['buy']
        
        # NEW API: All fields are required
        required_fields = ['balance_after', 'buy_price', 'contract_id', 'longcode', 
                          'payout', 'purchase_time', 'start_time', 'transaction_id']
        
        for field in required_fields:
            if field not in buy_data:
                current_app.logger.warning(f'Buy response missing field: {field}')
        
        parsed = {
            'balance_after': float(buy_data.get('balance_after', 0)),
            'buy_price': float(buy_data.get('buy_price', 0)),
            'contract_id': buy_data.get('contract_id'),
            'longcode': buy_data.get('longcode'),
            'payout': float(buy_data.get('payout', 0)),
            'purchase_time': buy_data.get('purchase_time'),
            'start_time': buy_data.get('start_time'),
            'transaction_id': buy_data.get('transaction_id'),
            'shortcode': buy_data.get('shortcode')
        }
        
        current_app.logger.info(
            f'✅ CONTRACT PURCHASED: ID={parsed["contract_id"]}, '
            f'Price=${parsed["buy_price"]:.2f}, Payout=${parsed["payout"]:.2f}'
        )
        
        return parsed
    
    @staticmethod
    def sell_contract(contract_id, price=0):
        """
        Sell an open contract before expiry.
        Returns WebSocket message to be sent (does NOT execute trade).
        
        ⚠️ CRITICAL: This method only prepares the message.
        The caller MUST obtain user confirmation before sending.
        
        Args:
            contract_id: Contract ID to sell (required)
            price: Minimum price willing to accept (default: 0 for market price, minimum: 0)
            
        Returns:
            dict: Sell message ready to send via WebSocket
            
        Raises:
            TradeServiceError: If parameters are invalid
            
        Example:
            # 1. Get user confirmation first
            if user_confirms:
                msg = TradeService.sell_contract(contract_id=123456, price=0)
                ws.send(json.dumps(msg))
        """
        # Validate contract ID
        if not contract_id:
            raise TradeServiceError('Contract ID is required', 'MISSING_CONTRACT_ID')
        
        # Validate price (NEW API: minimum 0)
        if not isinstance(price, (int, float)) or price < 0:
            raise TradeServiceError('Price must be a non-negative number (use 0 for market price)', 'INVALID_PRICE')
        
        # Build sell message (NEW API format - no loginid parameter)
        sell_message = {
            'sell': int(contract_id),
            'price': float(price)
        }
        
        current_app.logger.warning(
            f'⚠️ TRADE PREPARED: Sell contract {contract_id} at ${price:.2f} '
            f'- REQUIRES USER CONFIRMATION'
        )
        
        return sell_message
    
    @staticmethod
    def parse_sell_response(response_data):
        """
        Parse sell response from Deriv API.
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed sell data
            
        Raises:
            TradeServiceError: If response contains error or is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown sell error'),
                error.get('code', 'SELL_ERROR')
            )
        
        if 'sell' not in response_data:
            raise TradeServiceError('Invalid sell response: missing sell object', 'INVALID_RESPONSE')
        
        sell_data = response_data['sell']
        
        # NEW API: All 5 fields are now required
        required_fields = ['balance_after', 'contract_id', 'reference_id', 'sold_for', 'transaction_id']
        
        for field in required_fields:
            if field not in sell_data:
                current_app.logger.warning(f'Sell response missing required field: {field}')
        
        parsed = {
            'balance_after': float(sell_data.get('balance_after', 0)),
            'contract_id': sell_data.get('contract_id'),
            'reference_id': sell_data.get('reference_id'),
            'sold_for': float(sell_data.get('sold_for', 0)),
            'transaction_id': sell_data.get('transaction_id')
        }
        
        current_app.logger.info(
            f'✅ CONTRACT SOLD: ID={parsed["contract_id"]}, '
            f'Sold for=${parsed["sold_for"]:.2f}, Balance=${parsed["balance_after"]:.2f}'
        )
        
        return parsed
    
    @staticmethod
    def get_portfolio(contract_type=None):
        """
        Retrieve current portfolio (open positions).
        Returns WebSocket message to be sent.
        
        Args:
            contract_type: Optional list of contract types to filter (e.g., ['CALL', 'PUT'])
            
        Returns:
            dict: Portfolio message ready to send via WebSocket
            
        Example:
            # Get all open positions
            msg = TradeService.get_portfolio()
            ws.send(json.dumps(msg))
            
            # Filter by contract types
            msg = TradeService.get_portfolio(contract_type=['CALL', 'PUT'])
            ws.send(json.dumps(msg))
        """
        # Build portfolio message (NEW API format - no loginid parameter)
        portfolio_message = {
            'portfolio': 1
        }
        
        # Add optional contract type filter
        if contract_type and isinstance(contract_type, list):
            portfolio_message['contract_type'] = contract_type
        
        current_app.logger.info('Requesting portfolio (open positions)')
        
        return portfolio_message
    
    @staticmethod
    def parse_portfolio_response(response_data):
        """
        Parse portfolio response from Deriv API.
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed portfolio data with contracts list
            
        Raises:
            TradeServiceError: If response contains error or is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown portfolio error'),
                error.get('code', 'PORTFOLIO_ERROR')
            )
        
        if 'portfolio' not in response_data:
            raise TradeServiceError('Invalid portfolio response: missing portfolio object', 'INVALID_RESPONSE')
        
        portfolio = response_data['portfolio']
        contracts = portfolio.get('contracts', [])
        
        # Parse each contract (NEW API: underlying_symbol not symbol)
        parsed_contracts = []
        for contract in contracts:
            parsed_contract = {
                'app_id': contract.get('app_id'),  # NEW API: can no longer be null
                'buy_price': float(contract.get('buy_price', 0)),
                'contract_id': contract.get('contract_id'),
                'contract_type': contract.get('contract_type'),
                'currency': contract.get('currency'),
                'date_start': contract.get('date_start'),
                'expiry_time': contract.get('expiry_time'),
                'longcode': contract.get('longcode'),
                'payout': float(contract.get('payout', 0)),
                'purchase_time': contract.get('purchase_time'),
                'shortcode': contract.get('shortcode'),
                'transaction_id': contract.get('transaction_id'),
                'underlying_symbol': contract.get('underlying_symbol'),  # NEW API: renamed from 'symbol'
            }
            parsed_contracts.append(parsed_contract)
        
        current_app.logger.info(f'Retrieved {len(parsed_contracts)} open positions')
        
        return {
            'contracts': parsed_contracts,
            'count': len(parsed_contracts)
        }
    
    @staticmethod
    def get_proposal_open_contract(contract_id, subscribe=1):
        """
        Get real-time status of an open contract.
        Use this to track P&L and contract updates.
        
        Args:
            contract_id: Contract ID to track (required)
            subscribe: 1 for real-time updates, 0 for one-time fetch (default: 1)
            
        Returns:
            dict: Proposal open contract message ready to send via WebSocket
            
        Example:
            # Subscribe to contract updates
            msg = TradeService.get_proposal_open_contract(contract_id=123456)
            ws.send(json.dumps(msg))
        """
        if not contract_id:
            raise TradeServiceError('Contract ID is required', 'MISSING_CONTRACT_ID')
        
        # Build proposal_open_contract message (NEW API format - no loginid)
        message = {
            'proposal_open_contract': 1,
            'contract_id': int(contract_id),
            'subscribe': subscribe
        }
        
        current_app.logger.info(f'Requesting contract status for {contract_id}')
        
        return message
    
    @staticmethod
    def parse_proposal_open_contract_response(response_data):
        """
        Parse proposal_open_contract response from Deriv API.
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed contract status with P&L information
            
        Raises:
            TradeServiceError: If response contains error or is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown contract status error'),
                error.get('code', 'CONTRACT_STATUS_ERROR')
            )
        
        if 'proposal_open_contract' not in response_data:
            raise TradeServiceError(
                'Invalid response: missing proposal_open_contract object',
                'INVALID_RESPONSE'
            )
        
        contract = response_data['proposal_open_contract']
        
        # NEW API: contract_id, contract_type, and currency are now required
        required_fields = ['contract_id', 'contract_type', 'currency']
        for field in required_fields:
            if field not in contract:
                raise TradeServiceError(
                    f'Invalid response: missing required field {field}',
                    'INVALID_RESPONSE'
                )
        
        # Parse contract data (NEW API: handle string | number types)
        bid_price = contract.get('bid_price')
        buy_price = contract.get('buy_price')
        current_spot = contract.get('current_spot')
        profit = contract.get('profit')
        
        # Convert to float if present (handle both string and number)
        parsed = {
            'contract_id': contract.get('contract_id'),
            'contract_type': contract.get('contract_type'),
            'currency': contract.get('currency'),
            'bid_price': float(bid_price) if bid_price else None,
            'buy_price': float(buy_price) if buy_price else None,
            'current_spot': float(current_spot) if current_spot else None,
            'date_start': contract.get('date_start'),
            'entry_spot': contract.get('entry_spot'),
            'expiry_time': contract.get('expiry_time'),
            'is_expired': contract.get('is_expired', 0),
            'is_settleable': contract.get('is_settleable', 0),
            'is_sold': contract.get('is_sold', 0),
            'is_valid_to_sell': contract.get('is_valid_to_sell', 0),
            'longcode': contract.get('longcode'),
            'payout': float(contract.get('payout', 0)),  # NEW API: always string
            'profit': float(profit) if profit else 0,
            'profit_percentage': float(contract.get('profit_percentage', 0)) if contract.get('profit_percentage') else 0,
            'purchase_time': contract.get('purchase_time'),
            'sell_price': float(contract.get('sell_price', 0)) if contract.get('sell_price') else None,
            'sell_time': contract.get('sell_time'),
            'shortcode': contract.get('shortcode'),
            'status': contract.get('status'),
            'transaction_ids': contract.get('transaction_ids', {}),
            'underlying_symbol': contract.get('underlying'),  # May be 'underlying' or 'underlying_symbol'
            'subscription': response_data.get('subscription')
        }
        
        return parsed
    
    @staticmethod
    def get_profit_table(description=1, limit=50, offset=None, date_from=None, date_to=None, sort='DESC'):
        """
        Retrieve profit/loss table (trade history).
        Shows completed trades with their profit/loss.
        
        Args:
            description: Include description (1) or not (0) - default: 1
            limit: Maximum records to return (default: 50, max: 500)
            offset: Number of records to skip (for pagination)
            date_from: Start date (epoch or 'yyyy-mm-dd' format)
            date_to: End date (epoch or 'yyyy-mm-dd' format)
            sort: 'ASC' or 'DESC' (default: 'DESC')
            
        Returns:
            dict: Profit table message ready to send via WebSocket
            
        Example:
            # Get last 50 trades
            msg = TradeService.get_profit_table()
            
            # Get trades with pagination
            msg = TradeService.get_profit_table(limit=100, offset=50)
            
            # Get trades for date range
            msg = TradeService.get_profit_table(
                date_from='2024-01-01',
                date_to='2024-12-31'
            )
        """
        # Validate limit (NEW API: max 500)
        if limit > 500:
            current_app.logger.warning(f'Limit {limit} exceeds maximum 500, using 500')
            limit = 500
        
        # Build profit_table message (NEW API format - no loginid parameter)
        message = {
            'profit_table': 1,
            'description': description,
            'limit': limit,
            'sort': sort
        }
        
        # Add optional parameters
        if offset is not None:
            message['offset'] = offset
        if date_from:
            message['date_from'] = date_from
        if date_to:
            message['date_to'] = date_to
        
        current_app.logger.info(f'Requesting profit table (limit: {limit}, sort: {sort})')
        
        return message
    
    @staticmethod
    def parse_profit_table_response(response_data):
        """
        Parse profit_table response from Deriv API.
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed profit table with transactions list
            
        Raises:
            TradeServiceError: If response contains error or is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown profit table error'),
                error.get('code', 'PROFIT_TABLE_ERROR')
            )
        
        if 'profit_table' not in response_data:
            raise TradeServiceError(
                'Invalid profit table response: missing profit_table object',
                'INVALID_RESPONSE'
            )
        
        profit_table = response_data['profit_table']
        
        # NEW API: count and transactions are now required
        count = profit_table.get('count', 0)
        transactions = profit_table.get('transactions', [])
        
        # Parse each transaction (NEW API: all fields now required)
        parsed_transactions = []
        for txn in transactions:
            parsed_txn = {
                'app_id': txn.get('app_id'),  # NEW API: no longer nullable
                'buy_price': float(txn.get('buy_price', 0)),  # Required
                'contract_id': txn.get('contract_id'),
                'longcode': txn.get('longcode'),
                'payout': float(txn.get('payout', 0)),  # Required
                'purchase_time': txn.get('purchase_time'),  # Required
                'sell_price': float(txn.get('sell_price', 0)),  # Required
                'sell_time': txn.get('sell_time'),
                'shortcode': txn.get('shortcode'),
                'transaction_id': txn.get('transaction_id'),  # Required
                'profit_loss': float(txn.get('sell_price', 0)) - float(txn.get('buy_price', 0))
            }
            parsed_transactions.append(parsed_txn)
        
        current_app.logger.info(f'Retrieved {len(parsed_transactions)} trades from profit table')
        
        return {
            'count': count,
            'transactions': parsed_transactions
        }
    
    @staticmethod
    def get_statement(description=1, limit=50, offset=None, action_type=None, date_from=None, date_to=None):
        """
        Retrieve account statement (transaction history).
        Shows all account transactions including deposits, withdrawals, buys, and sells.
        
        Args:
            description: Include description (1) or not (0) - default: 1
            limit: Maximum records to return (default: 50, max: 500)
            offset: Number of records to skip (for pagination)
            action_type: Filter by type ('buy', 'sell', 'deposit', 'withdrawal', etc.)
            date_from: Start date (epoch or 'yyyy-mm-dd' format)
            date_to: End date (epoch or 'yyyy-mm-dd' format)
            
        Returns:
            dict: Statement message ready to send via WebSocket
            
        Example:
            # Get all transactions
            msg = TradeService.get_statement()
            
            # Get only buys and sells
            msg = TradeService.get_statement(action_type='buy')
            
            # Get deposits
            msg = TradeService.get_statement(action_type='deposit')
        """
        # Validate limit
        if limit > 500:
            current_app.logger.warning(f'Limit {limit} exceeds maximum 500, using 500')
            limit = 500
        
        # Build statement message (NEW API format - no loginid parameter)
        message = {
            'statement': 1,
            'description': description,
            'limit': limit
        }
        
        # Add optional parameters
        if offset is not None:
            message['offset'] = offset
        if action_type:
            message['action_type'] = action_type  # NEW API: accepts any string
        if date_from:
            message['date_from'] = date_from
        if date_to:
            message['date_to'] = date_to
        
        current_app.logger.info(f'Requesting statement (limit: {limit}, action_type: {action_type})')
        
        return message
    
    @staticmethod
    def parse_statement_response(response_data):
        """
        Parse statement response from Deriv API.
        
        Args:
            response_data: Response dictionary from WebSocket
            
        Returns:
            dict: Parsed statement with transactions list
            
        Raises:
            TradeServiceError: If response contains error or is invalid
        """
        if 'error' in response_data:
            error = response_data['error']
            raise TradeServiceError(
                error.get('message', 'Unknown statement error'),
                error.get('code', 'STATEMENT_ERROR')
            )
        
        if 'statement' not in response_data:
            raise TradeServiceError(
                'Invalid statement response: missing statement object',
                'INVALID_RESPONSE'
            )
        
        statement = response_data['statement']
        
        # NEW API: count and transactions are now required
        count = statement.get('count', 0)
        transactions = statement.get('transactions', [])
        
        # Parse each transaction (NEW API: required fields)
        parsed_transactions = []
        for txn in transactions:
            parsed_txn = {
                'action_type': txn.get('action_type'),  # Required
                'amount': float(txn.get('amount', 0)),  # Required
                'balance_after': float(txn.get('balance_after', 0)),  # Required
                'contract_id': txn.get('contract_id'),
                'longcode': txn.get('longcode'),
                'payout': float(txn.get('payout', 0)) if txn.get('payout') else None,
                'purchase_time': txn.get('purchase_time'),
                'reference_id': txn.get('reference_id'),
                'shortcode': txn.get('shortcode'),
                'transaction_id': txn.get('transaction_id'),  # Required
                'transaction_time': txn.get('transaction_time'),  # Required
            }
            parsed_transactions.append(parsed_txn)
        
        current_app.logger.info(f'Retrieved {len(parsed_transactions)} transactions from statement')
        
        return {
            'count': count,
            'transactions': parsed_transactions
        }


class TradeServiceError(Exception):
    """
    Custom exception for trade service errors.
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
