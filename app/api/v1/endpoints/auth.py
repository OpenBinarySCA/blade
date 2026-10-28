"""
Authentication API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from ..schemas import GoogleLoginRequest, TokenResponse, UserResponse
from ....services.auth import login_with_google, require_auth
from ....databases.user_data.models import User


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/google", response_model=TokenResponse)
def google_login(body: GoogleLoginRequest):
    """
    Authenticate with Google OAuth

    - Receives Google ID token from frontend
    - Verifies token with Google
    - Creates or retrieves user
    - Returns JWT access token
    """
    try:
        access_token = login_with_google(body.id_token)
        return TokenResponse(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.get("/me", response_model=UserResponse)
def get_current_user(user: User = Depends(require_auth)):
    """
    Get current authenticated user information
    """
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        profile_picture=user.profile_picture,
        is_admin=user.is_admin
    )


@router.post("/logout")
def logout():
    """
    Logout endpoint

    Note: Since we use stateless JWT, logout is handled on frontend
    by removing the token from localStorage. This endpoint is for
    consistency and future use (e.g., token blacklisting).
    """
    return {"message": "Logged out successfully"}
