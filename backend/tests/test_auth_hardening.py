import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from config import get_settings
from models.base import db_manager
from models.user import UserModel

@pytest.fixture(autouse=True)
async def setup_test_db():
    # Initialize database if not done
    await db_manager.init()
    # Disable foreign keys temporarily for clean teardown
    await db_manager.execute("PRAGMA foreign_keys=OFF")
    await db_manager.execute("DELETE FROM refresh_tokens")
    await db_manager.execute("DELETE FROM users")
    await db_manager.execute("PRAGMA foreign_keys=ON")
    yield
    await db_manager.execute("PRAGMA foreign_keys=OFF")
    await db_manager.execute("DELETE FROM refresh_tokens")
    await db_manager.execute("DELETE FROM users")
    await db_manager.execute("PRAGMA foreign_keys=ON")
    await db_manager.close()

def test_production_environment_validation():
    from services.validation import validate_environment
    settings = get_settings()
    
    orig_env = settings.app_env
    orig_key = settings.secret_key
    orig_sec = settings.security_enabled
    orig_pass = settings.admin_initial_password
    
    try:
        settings.app_env = "production"
        settings.secret_key = "secure-prod-key-goes-here-and-is-long"
        settings.security_enabled = True
        settings.admin_initial_password = None
        
        with pytest.raises(RuntimeError) as exc:
            validate_environment()
        assert "ADMIN_INITIAL_PASSWORD is required" in str(exc.value)
        
        settings.admin_initial_password = "secure_password"
        validate_environment()
        
    finally:
        settings.app_env = orig_env
        settings.secret_key = orig_key
        settings.security_enabled = orig_sec
        settings.admin_initial_password = orig_pass

@pytest.mark.asyncio
async def test_auth_hardening_flow():
    settings = get_settings()
    orig_sec = settings.security_enabled
    settings.security_enabled = True
    
    settings.admin_initial_password = "secure_admin_password_123"
    
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), 
            base_url="http://test",
            headers={"X-API-Key": "dev-local-key-12345"}
        ) as client:
            await UserModel.ensure_default_user()
            user = await UserModel.get_by_username("admin")
            assert user is not None
            assert user["password_change_required"] is True
            
            # 2. Login
            login_res = await client.post("/api/auth/login", json={
                "username": "admin",
                "password": "secure_admin_password_123"
            })
            assert login_res.status_code == 200
            data = login_res.json()
            assert "access_token" in data
            assert "csrf_token" in data
            assert data["user"]["password_change_required"] is True
            
            # Get response cookies
            refresh_cookie = login_res.cookies.get("refresh_token")
            assert refresh_cookie is not None
            csrf_token = data["csrf_token"]
            access_token = data["access_token"]
            
            # 3. Access authenticated route with JWT
            me_res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
            assert me_res.status_code == 200
            assert me_res.json()["username"] == "admin"
            
            # 4. Refresh token rotation without CSRF header should fail
            refresh_fail = await client.post("/api/auth/refresh")
            assert refresh_fail.status_code == 401
            
            # Refresh token rotation with wrong CSRF header should fail
            refresh_fail_csrf = await client.post("/api/auth/refresh", headers={"X-CSRF-Token": "wrong_csrf"})
            assert refresh_fail_csrf.status_code == 401
            
            # 5. Refresh token rotation with correct CSRF header should pass
            refresh_pass = await client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf_token})
            assert refresh_pass.status_code == 200
            refresh_data = refresh_pass.json()
            assert "access_token" in refresh_data
            assert "csrf_token" in refresh_data
            
            new_access_token = refresh_data["access_token"]
            new_csrf_token = refresh_data["csrf_token"]
            new_refresh_cookie = refresh_pass.cookies.get("refresh_token")
            assert new_refresh_cookie is not None
            assert new_refresh_cookie != refresh_cookie  # Assert rotation occurred
            
            # 6. Change Password
            change_res = await client.post("/api/auth/change-password", 
                json={
                    "old_password": "secure_admin_password_123",
                    "new_password": "brand_new_admin_password_456"
                },
                headers={
                    "Authorization": f"Bearer {new_access_token}",
                    "X-CSRF-Token": new_csrf_token
                }
            )
            assert change_res.status_code == 200
            
            # Verify password_change_required is now False
            user_after = await UserModel.get_by_username("admin")
            assert user_after["password_change_required"] is False
            
            # Verify previous refresh token is revoked
            client.cookies.set("refresh_token", new_refresh_cookie)
            refresh_after_change = await client.post("/api/auth/refresh", headers={"X-CSRF-Token": new_csrf_token})
            assert refresh_after_change.status_code == 401
            
            # 7. Login with new password
            login_new = await client.post("/api/auth/login", json={
                "username": "admin",
                "password": "brand_new_admin_password_456"
            })
            assert login_new.status_code == 200
            new_data = login_new.json()
            assert new_data["user"]["password_change_required"] is False
            
            final_refresh_cookie = login_new.cookies.get("refresh_token")
            final_csrf_token = new_data["csrf_token"]
            
            # 8. Logout
            client.cookies.set("refresh_token", final_refresh_cookie)
            logout_res = await client.post("/api/auth/logout", headers={"X-CSRF-Token": final_csrf_token})
            assert logout_res.status_code == 200
            
            # Verify refresh cookie is cleared
            cleared_cookie = logout_res.cookies.get("refresh_token")
            assert cleared_cookie is None or cleared_cookie == ""
            
            # Verify refresh token in DB is revoked
            refresh_after_logout = await client.post("/api/auth/refresh", headers={"X-CSRF-Token": final_csrf_token})
            assert refresh_after_logout.status_code == 401

    finally:
        settings.security_enabled = orig_sec
