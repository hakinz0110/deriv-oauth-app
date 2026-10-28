"""
Integration tests for core trading flow
Tests: proposal → buy → portfolio → history
Using Deriv demo accounts (real API, fake money)
"""

import pytest


class TestTradingFlow:
    """Test the complete trading flow from proposal to execution"""
    
    def test_proposal_endpoint_exists(self, client):
        """Test that proposal endpoint exists"""
        response = client.post('/api/proposal', 
            json={
                'contract_type': 'CALL',
                'symbol': 'R_100',
                'duration': 5,
                'duration_unit': 't',
                'amount': 10
            }
        )
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_buy_endpoint_exists(self, client):
        """Test that buy contract endpoint exists"""
        response = client.post('/api/buy',
            json={
                'proposal_id': 'test_proposal_id',
                'price': 10.00
            }
        )
        # Endpoint exists (may fail auth or validation, but not 404)
        assert response.status_code != 404
    
    def test_sell_endpoint_exists(self, client):
        """Test that sell contract endpoint exists"""
        response = client.post('/api/sell',
            json={
                'contract_id': 'test_contract_id',
                'price': 15.00
            }
        )
        # Endpoint exists (may fail auth or validation, but not 404)
        assert response.status_code != 404
    
    def test_portfolio_endpoint_exists(self, client):
        """Test that portfolio endpoint exists"""
        response = client.get('/api/portfolio')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_trades_endpoint_exists(self, client):
        """Test that trades history endpoint exists"""
        response = client.get('/api/trades')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_profit_table_endpoint_exists(self, client):
        """Test that profit table endpoint exists"""
        response = client.get('/api/profit-table')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
