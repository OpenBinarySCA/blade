"""
OAuth Connection Repository - CRUD operations for OAuthConnection model
"""
from typing import Optional, List
from datetime import datetime

from sqlalchemy.orm import joinedload

from ..models import OAuthConnection
from ..database import session_generator


def get_oauth_connection(user_id: int, provider: str) -> Optional[OAuthConnection]:
    """Get OAuth connection for a specific user and provider"""
    with session_generator() as db:
        return db.query(OAuthConnection).options(
            joinedload(OAuthConnection.user)
        ).filter(
            OAuthConnection.user_id == user_id,
            OAuthConnection.provider == provider
        ).first()


def get_oauth_connection_by_provider_user_id(provider: str, provider_user_id: str) -> Optional[OAuthConnection]:
    """Get OAuth connection by provider and provider user ID (e.g., Google ID)"""
    with session_generator() as db:
        return db.query(OAuthConnection).options(
            joinedload(OAuthConnection.user)
        ).filter(
            OAuthConnection.provider == provider,
            OAuthConnection.provider_user_id == provider_user_id
        ).first()


def get_user_oauth_connections(user_id: int) -> List[OAuthConnection]:
    """Get all OAuth connections for a user"""
    with session_generator() as db:
        return db.query(OAuthConnection).filter(
            OAuthConnection.user_id == user_id
        ).all()


def create_oauth_connection(
    user_id: int,
    provider: str,
    provider_user_id: str,
    access_token: str = None,
    refresh_token: str = None,
    token_expires_at: datetime = None,
    profile_data: str = None
) -> OAuthConnection:
    """Create a new OAuth connection"""
    with session_generator() as db:
        oauth_conn = OAuthConnection(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            profile_data=profile_data
        )
        db.add(oauth_conn)
        db.commit()
        db.refresh(oauth_conn)
        return oauth_conn


def update_oauth_connection(
    oauth_connection_id: int,
    access_token: str = None,
    refresh_token: str = None,
    token_expires_at: datetime = None,
    profile_data: str = None
) -> Optional[OAuthConnection]:
    """Update OAuth connection tokens and profile data"""
    with session_generator() as db:
        oauth_conn = db.query(OAuthConnection).filter(
            OAuthConnection.id == oauth_connection_id
        ).first()

        if oauth_conn:
            if access_token is not None:
                oauth_conn.access_token = access_token
            if refresh_token is not None:
                oauth_conn.refresh_token = refresh_token
            if token_expires_at is not None:
                oauth_conn.token_expires_at = token_expires_at
            if profile_data is not None:
                oauth_conn.profile_data = profile_data

            db.commit()
            db.refresh(oauth_conn)

        return oauth_conn


def delete_oauth_connection(user_id: int, provider: str) -> bool:
    """Delete OAuth connection for a user and provider"""
    with session_generator() as db:
        oauth_conn = db.query(OAuthConnection).filter(
            OAuthConnection.user_id == user_id,
            OAuthConnection.provider == provider
        ).first()

        if oauth_conn:
            db.delete(oauth_conn)
            db.commit()
            return True

        return False
