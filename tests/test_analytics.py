"""
Integration tests for analytics endpoints
Tests performance metrics and visualizations
"""

import pytest


class TestAnalytics:
    """Test analytics and performance metrics"""
    
    def test_analytics_overview_endpoint_exists(self, client):
        """Test that analytics overview endpoint exists"""
        response = client.get('/api/analytics/overview')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_win_rate_endpoint_exists(self, client):
        """Test that win rate endpoint exists"""
        response = client.get('/api/analytics/win-rate')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_profit_factor_endpoint_exists(self, client):
        """Test that profit factor endpoint exists"""
        response = client.get('/api/analytics/profit-factor')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_max_drawdown_endpoint_exists(self, client):
        """Test that max drawdown endpoint exists"""
        response = client.get('/api/analytics/max-drawdown')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_expectancy_endpoint_exists(self, client):
        """Test that expectancy endpoint exists"""
        response = client.get('/api/analytics/expectancy')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_by_symbol_endpoint_exists(self, client):
        """Test that symbol performance endpoint exists"""
        response = client.get('/api/analytics/by-symbol')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_by_strategy_endpoint_exists(self, client):
        """Test that strategy performance endpoint exists"""
        response = client.get('/api/analytics/by-strategy')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_equity_curve_endpoint_exists(self, client):
        """Test that equity curve endpoint exists"""
        response = client.get('/api/analytics/equity-curve')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_daily_pnl_endpoint_exists(self, client):
        """Test that daily P/L endpoint exists"""
        response = client.get('/api/analytics/daily-pnl')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_symbols_endpoint_exists(self, client):
        """Test that symbols data endpoint exists"""
        response = client.get('/api/analytics/symbols')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_top_strategies_endpoint_exists(self, client):
        """Test that top strategies endpoint exists"""
        response = client.get('/api/analytics/top-strategies')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
    
    def test_analytics_sync_endpoint_exists(self, client):
        """Test that analytics sync endpoint exists"""
        response = client.post('/api/analytics/sync')
        # Endpoint exists (may fail auth, but not 404)
        assert response.status_code != 404
