"""
User Repository - CRUD operations for User model
"""
from typing import Optional

from ..models import User
from ..database import session_generator


def get_user_by_username(username: str) -> Optional[User]:
    """Get user by username"""
    with session_generator() as db:
        return db.query(User).filter(User.username == username).first()


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID"""
    with session_generator() as db:
        return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(email: str) -> Optional[User]:
    """Get user by email"""
    with session_generator() as db:
        return db.query(User).filter(User.email == email).first()


def create_user(
    username: str,
    email: str = None,
    full_name: str = None,
    profile_picture: str = None,
    is_admin: bool = False
) -> User:
    """Create a new user"""
    with session_generator() as db:
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            profile_picture=profile_picture,
            is_admin=is_admin
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def update_user_profile(
    user_id: int,
    full_name: str = None,
    profile_picture: str = None
) -> Optional[User]:
    """Update user profile information"""
    with session_generator() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if full_name is not None:
                user.full_name = full_name
            if profile_picture is not None:
                user.profile_picture = profile_picture
            db.commit()
            db.refresh(user)
        return user


def get_all_users(
    page: int = 1,
    page_size: int = 20,
    search: str = None,
    is_admin: bool = None
) -> tuple[list[User], int]:
    """
    Get all users with pagination and filtering

    Returns:
        Tuple of (users list, total count)
    """
    with session_generator() as db:
        query = db.query(User)

        # Apply filters
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (User.username.ilike(search_pattern)) |
                (User.email.ilike(search_pattern)) |
                (User.full_name.ilike(search_pattern))
            )

        if is_admin is not None:
            query = query.filter(User.is_admin == is_admin)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

        return users, total


def update_user_admin_status(user_id: int, is_admin: bool) -> Optional[User]:
    """Update user admin status"""
    with session_generator() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_admin = is_admin
            db.commit()
            db.refresh(user)
        return user


def delete_user(user_id: int) -> bool:
    """Delete a user and all related data"""
    with session_generator() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False


def get_user_count() -> int:
    """Get total user count"""
    with session_generator() as db:
        return db.query(User).count()


def get_admin_count() -> int:
    """Get admin user count"""
    with session_generator() as db:
        return db.query(User).filter(User.is_admin == True).count()
