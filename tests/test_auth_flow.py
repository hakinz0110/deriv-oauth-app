"""
Integration tests for authentication flow
Tests the complete OAuth login flow with Deriv demo accounts
"""

import pytest


class TestAuthenticationFlow:
    """Test authentication and account management"""
    
    def test_index_page_loads(self, client):
        """Test that the index/onboarding page loads"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'onboard' in response.data.lower() or b'HTS' in response.data or b'Trade' in response.data
    
    def test_login_page_loads(self, client):
        """Test that login page loads"""
        response = client.get('/login')
        assert response.status_code == 200
    
    def test_login_redirect_to_oauth(self, client):
        """Test that login redirects to OAuth (or mock in test mode)"""
        response = client.get('/login?direct=1', follow_redirects=False)
        # In test mode with MOCK_OAUTH=True, should redirect to callback
        assert response.status_code in [302, 200]
    
    def test_callback_endpoint_exists(self, client):
        """Test that OAuth callback endpoint exists"""
        # This will fail without valid tokens, but endpoint should exist
        response = client.get('/callback')
        # Should either redirect or show an error (not 404)
        assert response.status_code != 404
    
    def test_dashboard_requires_auth(self, client):
        """Test that dashboard requires authentication"""
        response = client.get('/dashboard', follow_redirects=False)
        # Should redirect to login if not authenticated
        assert response.status_code in [302, 401, 403] or b'login' in response.data.lower()
