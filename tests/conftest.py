"""
Pytest configuration and fixtures for HTS Trade testing
"""

import pytest
import os
from app import create_app

@pytest.fixture
def app():
    """Create and configure a test Flask application instance."""
    # Set test configuration
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['FLASK_DEBUG'] = 'False'
    os.environ['MOCK_OAUTH'] = 'True'  # Use mock OAuth for testing
    
    app = create_app()
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
    })
    
    yield app


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner for the Flask application."""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers():
    """Provide mock authentication headers for testing."""
    return {
        'Cookie': 'session=mock_session_token'
    }


@pytest.fixture
def mock_deriv_demo_account():
    """Mock Deriv demo account data."""
    return {
        'account_id': 'VRTC1234567',
        'account_type': 'demo',
        'currency': 'USD',
        'balance': 10000.00,
        'loginid': 'VRTC1234567'
    }


@pytest.fixture
def mock_trading_system():
    """Mock trading system data for testing."""
    return {
        'name': 'Test RSI System',
        'description': 'Test system for unit testing',
        'contract_type': 'CALL',
        'symbol': 'R_100',
        'duration': 5,
        'duration_unit': 't',
        'entry_strategy_type': 'rsi',
        'entry_conditions': {
            'indicator': 'rsi',
            'period': 14,
            'overbought': 70,
            'oversold': 30
        },
        'entry_logic': 'AND',
        'position_sizing_type': 'fixed',
        'position_sizing_config': {
            'base_stake': 10.00
        },
        'exit_strategy_type': 'contract_end',
        'exit_conditions': {}
    }
