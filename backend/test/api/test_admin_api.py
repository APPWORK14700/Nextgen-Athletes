import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.exceptions import AuthorizationError


class TestAdminAPI:
    """Test cases for admin API endpoints"""
    
    def test_search_users_success(self, client, mock_admin_user):
        """Test searching users successfully (admin only)"""
        with patch('app.api.v1.admin.require_admin_role', return_value=mock_admin_user):
            with patch('app.api.v1.admin.user_service.search_users_admin') as mock_search:
                mock_search.return_value = {
                    "users": [
                        {"uid": "user1", "email": "user1@example.com", "role": "athlete"},
                        {"uid": "user2", "email": "user2@example.com", "role": "scout"}
                    ],
                    "total": 2,
                    "page": 1,
                    "limit": 20
                }
                
                response = client.get("/api/v1/admin/users")
                
                assert response.status_code == 200
                data = response.json()
                assert len(data["users"]) == 2
                assert data["total"] == 2
    
    def test_update_user_status_success(self, client, mock_admin_user):
        """Test updating user status successfully (admin only)"""
        with patch('app.api.v1.admin.require_admin_role', return_value=mock_admin_user):
            with patch('app.api.v1.admin.user_service.update_user_status_admin') as mock_update:
                mock_update.return_value = {
                    "uid": "user123",
                    "status": "suspended",
                    "updated_by": "admin_user_id"
                }
                
                response = client.put("/api/v1/admin/users/user123/status", data={"status": "suspended"})
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "suspended"
                assert data["updated_by"] == "admin_user_id"
    
    def test_get_admin_stats_success(self, client, mock_admin_user):
        """Test getting admin stats successfully (admin only)"""
        with patch('app.api.v1.admin.require_admin_role', return_value=mock_admin_user):
            with patch('app.api.v1.admin.user_service.get_admin_stats_overview') as mock_stats:
                mock_stats.return_value = {
                    "total_users": 1000,
                    "total_athletes": 600,
                    "total_scouts": 400,
                    "active_opportunities": 50
                }
                
                response = client.get("/api/v1/admin/stats/overview")
                
                assert response.status_code == 200
                data = response.json()
                assert data["total_users"] == 1000
                assert data["total_athletes"] == 600
                assert data["total_scouts"] == 400
    
    def test_admin_access_denied(self, client, mock_athlete_user):
        """Test that non-admin users are denied access"""
        with patch('app.api.v1.admin.require_admin_role') as mock_admin:
            mock_admin.side_effect = AuthorizationError("Admin access required")
            
            response = client.get("/api/v1/admin/users")
            
            assert response.status_code == 403
            assert "Admin access required" in response.json()["detail"] 