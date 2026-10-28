"""
User Data Repository Module
"""
from .user_repository import (
    get_user_by_username,
    get_user_by_id,
    get_user_by_email,
    create_user,
    update_user_profile,
    get_all_users,
    update_user_admin_status,
    delete_user,
    get_user_count,
    get_admin_count,
)
from .oauth_repository import (
    get_oauth_connection,
    get_oauth_connection_by_provider_user_id,
    get_user_oauth_connections,
    create_oauth_connection,
    update_oauth_connection,
    delete_oauth_connection,
)
from . import task_repository
from . import guest_repository
from . import settings_repository
from . import sample_repository

__all__ = [
    # User
    'get_user_by_username',
    'get_user_by_id',
    'get_user_by_email',
    'create_user',
    'update_user_profile',
    'get_all_users',
    'update_user_admin_status',
    'delete_user',
    'get_user_count',
    'get_admin_count',
    # OAuth
    'get_oauth_connection',
    'get_oauth_connection_by_provider_user_id',
    'get_user_oauth_connections',
    'create_oauth_connection',
    'update_oauth_connection',
    'delete_oauth_connection',
    # Task
    'task_repository',
    # Guest
    'guest_repository',
    # Settings
    'settings_repository',
    # Sample
    'sample_repository',
]
