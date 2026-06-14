"""
Auth Routes — Phase 5: /api/auth/*
------------------------------------
POST /api/auth/register       → create account
POST /api/auth/login          → return JWT + set HttpOnly refresh token
POST /api/auth/refresh        → rotate refresh token + yield access token
POST /api/auth/change-password → update credentials
POST /api/auth/logout         → delete session cookie
"""

from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional

from services.auth_service import auth_service, require_user
from config import get_settings
from models.base import db_manager

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username:     str = Field(..., min_length=3, max_length=50)
    password:     str = Field(..., min_length=6)
    email:        str = Field("", max_length=200)
    display_name: str = Field("", max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/auth/register", summary="Register a new account")
async def register(body: RegisterRequest):
    user = await auth_service.register(
        username=body.username,
        password=body.password,
        email=body.email,
        display_name=body.display_name,
    )
    return {"message": "Account created successfully.", "user": user}


@router.post("/auth/login", summary="Login and get JWT token")
async def login(body: LoginRequest, response: Response):
    res = await auth_service.login(body.username, body.password)
    user_id = res["user"]["id"]
    
    # Generate refresh token and CSRF token
    refresh_token, csrf_token = await auth_service.create_refresh_token(user_id)
    
    settings = get_settings()
    
    # Set secure cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        max_age=30 * 24 * 60 * 60, # 30 days
    )
    
    # Include csrf_token in response
    res["csrf_token"] = csrf_token
    
    if "user" in res:
        from routes.stream import system_events_manager
        await system_events_manager.broadcast({
            "event": "user_changed",
            "user_id": res["user"]["id"],
            "username": res["user"]["username"]
        })
    return res


@router.get("/auth/me", summary="Get current user profile")
async def me(current_user: dict = Depends(require_user)):
    return current_user


@router.post("/auth/refresh", summary="Get a fresh access token using refresh token")
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    csrf_token = request.headers.get("X-CSRF-Token")
    
    if not refresh_token or not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token or CSRF token"
        )
        
    user = await auth_service.verify_refresh_token(refresh_token, csrf_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token / CSRF token"
        )
        
    # Rotate token: revoke old refresh token
    await auth_service.revoke_refresh_token(refresh_token)
    
    # Create new refresh token + CSRF token
    new_refresh_token, new_csrf_token = await auth_service.create_refresh_token(user["id"])
    
    settings = get_settings()
    
    # Set new secure cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="strict",
        max_age=30 * 24 * 60 * 60,
    )
    
    # Generate fresh access token
    from services.auth_service import create_access_token
    access_token = create_access_token({"sub": user["id"], "username": user["username"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": new_csrf_token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "standard"),
            "password_change_required": bool(user.get("password_change_required", 0)),
        }
    }


@router.post("/auth/change-password", summary="Change user password")
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(require_user)):
    user_id = current_user["id"]
    
    row = await db_manager.fetch_one("SELECT hashed_password FROM users WHERE id = ?", (user_id,))
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
        
    hashed_pwd = row.get("hashed_password", "")
    from services.auth_service import verify_password, hash_password
    if not verify_password(body.old_password, hashed_pwd):
        raise HTTPException(status_code=400, detail="Invalid old password.")
        
    new_hashed = hash_password(body.new_password)
    
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db_manager.execute(
        "UPDATE users SET hashed_password = ?, password_change_required = 0, updated_at = ? WHERE id = ?",
        (new_hashed, now, user_id)
    )
    
    # Revoke all active refresh tokens for this user
    await db_manager.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
    
    return {"message": "Password changed successfully. All other sessions have been logged out."}


@router.post("/auth/logout", summary="Logout and clear refresh token")
async def logout(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    csrf_token = request.headers.get("X-CSRF-Token")
    
    if refresh_token:
        if not csrf_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSRF token required for logout"
            )
        user = await auth_service.verify_refresh_token(refresh_token, csrf_token)
        if user:
            await auth_service.revoke_refresh_token(refresh_token)
            
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=get_settings().app_env == "production",
        samesite="strict"
    )
    return {"message": "Logged out successfully."}
