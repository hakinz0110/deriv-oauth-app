"""
Integration tests for admin panel
Tests admin-only endpoints and access control
"""

import pytest


class TestAdminPanel:
    """Test admin panel functionality"""
    
    def test_admin_dashboard_endpoint_exists(self, client):
        """Test that admin dashboard endpoint exists"""
        response = client.get('/admin')
        # Endpoint exists (should require auth and admin role)
        # May return 401/403 (unauthorized) but not 404
        assert response.status_code != 404
    
    def test_admin_statistics_endpoint_exists(self, client):
        """Test that admin statistics endpoint exists"""
        response = client.get('/api/admin/statistics')
        # Endpoint exists (may fail auth/admin check, but not 404)
        assert response.status_code != 404
    
    def test_admin_users_endpoint_exists(self, client):
        """Test that admin users endpoint exists"""
        response = client.get('/api/admin/users')
        # Endpoint exists (may fail auth/admin check, but not 404)
        assert response.status_code != 404
    
    def test_admin_health_endpoint_exists(self, client):
        """Test that admin health endpoint exists"""
        response = client.get('/api/admin/health')
        # Endpoint exists (may fail auth/admin check, but not 404)
        assert response.status_code != 404
    
    def test_admin_top_performers_endpoint_exists(self, client):
        """Test that admin top performers endpoint exists"""
        response = client.get('/api/admin/top-performers')
        # Endpoint exists (may fail auth/admin check, but not 404)
        assert response.status_code != 404
    
    def test_admin_errors_endpoint_exists(self, client):
        """Test that admin errors endpoint exists"""
        response = client.get('/api/admin/errors')
        # Endpoint exists (may fail auth/admin check, but not 404)
        assert response.status_code != 404
    
    def test_admin_requires_authentication(self, client):
        """Test that admin endpoints require authentication"""
        response = client.get('/admin')
        # Should return 401 (unauthorized) or 403 (forbidden) or redirect
        # Should NOT return 200 (success) without auth
        assert response.status_code in [302, 401, 403] or b'login' in response.data.lower() or b'unauthorized' in response.data.lower()
