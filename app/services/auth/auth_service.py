"""
Authentication Service

Google OAuth 认证服务
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from google.oauth2 import id_token
from google.auth.transport import requests
from loguru import logger

from ...config import settings
from ...databases.user_data.models import User
from ...databases.user_data.repository import (
    get_user_by_username,
    get_user_by_email,
    create_user,
    update_user_profile,
    get_oauth_connection_by_provider_user_id,
    create_oauth_connection,
)


# Security scheme for JWT
security = HTTPBearer(auto_error=False)


def _create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.AUTH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.AUTH_SECRET, algorithm="HS256")
    return encoded_jwt


def login_with_google(google_token: str) -> str:
    """
    Authenticate user with Google ID token and issue JWT token

    Args:
        google_token: Google ID token from frontend

    Returns:
        JWT access token
    """
    # Verify Google configuration
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth not configured"
        )

    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(
            google_token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID
        )

        # Extract user info from Google token
        google_user_id = idinfo['sub']
        email = idinfo.get('email')
        full_name = idinfo.get('name')
        profile_picture = idinfo.get('picture')
        email_verified = idinfo.get('email_verified', False)

        if not email or not email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not verified by Google"
            )

        # Check if OAuth connection already exists by Google ID
        oauth_conn = get_oauth_connection_by_provider_user_id(
            provider="google",
            provider_user_id=google_user_id
        )

        if oauth_conn:
            # OAuth connection exists, get the user
            user = oauth_conn.user
            logger.info(f"User {user.username} logged in via existing Google connection")
        else:
            # No OAuth connection exists, check if user exists with this email (account linking)
            existing_user = get_user_by_email(email)
            if existing_user:
                # Link Google account to existing user
                create_oauth_connection(
                    user_id=existing_user.id,
                    provider="google",
                    provider_user_id=google_user_id
                )
                # Update user profile if not already set
                if (not existing_user.full_name and full_name) or (not existing_user.profile_picture and profile_picture):
                    update_user_profile(
                        user_id=existing_user.id,
                        full_name=full_name if not existing_user.full_name else None,
                        profile_picture=profile_picture if not existing_user.profile_picture else None
                    )
                user = existing_user
                logger.info(f"Linked Google account to existing user {user.username}")
            else:
                # Check if email is in admin list
                is_admin = email.lower() in [e.lower() for e in settings.ADMIN_EMAILS]

                # Create new user from Google
                user = create_user(
                    username=email,
                    email=email,
                    full_name=full_name,
                    profile_picture=profile_picture,
                    is_admin=is_admin
                )
                # Create OAuth connection
                create_oauth_connection(
                    user_id=user.id,
                    provider="google",
                    provider_user_id=google_user_id
                )
                logger.info(f"Created new user {user.username} via Google OAuth")

        # Generate JWT token
        session_id = str(uuid.uuid4())
        token_claims = {
            "sub": user.username,
            "user_id": user.id,
            "session_id": session_id,
            "is_admin": user.is_admin
        }
        access_token = _create_access_token(
            data=token_claims,
            expires_delta=timedelta(hours=settings.AUTH_TOKEN_EXPIRE_HOURS)
        )

        return access_token

    except ValueError as e:
        logger.warning(f"Invalid Google token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google authentication failed: {str(e)}"
        )


def get_current_user_from_token(token: str) -> User:
    """
    Validate JWT token and return the user

    Args:
        token: JWT token string

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        payload = jwt.decode(token, settings.AUTH_SECRET, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        user = get_user_by_username(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[User]:
    """
    FastAPI dependency to get current user from Authorization header

    Returns None if no token provided (for optional auth endpoints)
    """
    if not credentials:
        return None
    return get_current_user_from_token(credentials.credentials)


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[User]:
    """
    FastAPI dependency for optional authentication

    Returns:
        - User object if valid token provided
        - None if no token or invalid token (no exception raised)
    """
    if not credentials:
        return None
    try:
        return get_current_user_from_token(credentials.credentials)
    except HTTPException:
        # Invalid token - treat as no auth for optional endpoints
        return None
    except Exception:
        return None


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to require authentication

    Raises 401 if not authenticated
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return get_current_user_from_token(credentials.credentials)


async def require_admin(request: Request) -> User:
    """
    FastAPI dependency to require admin privileges

    Args:
        request: FastAPI Request object

    Returns:
        User object if admin

    Raises:
        HTTPException: 401 if not authenticated, 403 if not admin
    """
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token"
        )

    token = auth_header.split(" ", 1)[1]
    user = get_current_user_from_token(token)

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return user
