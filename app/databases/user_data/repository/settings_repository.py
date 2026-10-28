"""
System Settings Repository

数据库操作层，负责 system_settings 表的 CRUD 操作
"""
from typing import Optional
from loguru import logger

from ..database import session_generator
from ..models import SystemSetting


def get_setting(key: str) -> Optional[SystemSetting]:
    """获取单个设置项"""
    with session_generator() as session:
        return session.query(SystemSetting).filter(SystemSetting.key == key).first()


def get_setting_value(key: str, default=None):
    """获取设置值，返回正确类型"""
    setting = get_setting(key)
    if setting is None:
        return default
    return setting.get_typed_value()


def get_all_settings() -> list[SystemSetting]:
    """获取所有设置项"""
    with session_generator() as session:
        return session.query(SystemSetting).order_by(SystemSetting.category, SystemSetting.key).all()


def get_settings_by_category(category: str) -> list[SystemSetting]:
    """按分类获取设置项"""
    with session_generator() as session:
        return session.query(SystemSetting).filter(
            SystemSetting.category == category
        ).order_by(SystemSetting.key).all()


def get_public_settings() -> list[SystemSetting]:
    """获取所有公开设置项"""
    with session_generator() as session:
        return session.query(SystemSetting).filter(
            SystemSetting.is_public == True
        ).order_by(SystemSetting.category, SystemSetting.key).all()


def upsert_setting(
    key: str,
    value: str,
    value_type: str = "str",
    category: str = "general",
    description: Optional[str] = None,
    is_public: bool = False
) -> SystemSetting:
    """
    创建或更新设置项

    Args:
        key: 设置项键名
        value: 设置值（字符串形式）
        value_type: 值类型 (int, bool, str, json)
        category: 分类
        description: 描述
        is_public: 是否公开

    Returns:
        更新后的设置项
    """
    with session_generator() as session:
        setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()

        if setting is None:
            setting = SystemSetting(
                key=key,
                value=value,
                value_type=value_type,
                category=category,
                description=description,
                is_public=is_public
            )
            session.add(setting)
            logger.info(f"Created new setting: {key}")
        else:
            setting.value = value
            if value_type:
                setting.value_type = value_type
            if category:
                setting.category = category
            if description is not None:
                setting.description = description
            setting.is_public = is_public
            logger.info(f"Updated setting: {key}")

        session.flush()
        session.refresh(setting)
        return setting


def update_setting_value(key: str, value: str) -> Optional[SystemSetting]:
    """
    仅更新设置值

    Args:
        key: 设置项键名
        value: 新值（字符串形式）

    Returns:
        更新后的设置项，如果不存在返回 None
    """
    with session_generator() as session:
        setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()

        if setting is None:
            logger.warning(f"Setting not found: {key}")
            return None

        setting.value = value
        session.flush()
        session.refresh(setting)
        logger.info(f"Updated setting value: {key} = {value}")
        return setting


def delete_setting(key: str) -> bool:
    """
    删除设置项

    Returns:
        是否删除成功
    """
    with session_generator() as session:
        setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()

        if setting is None:
            return False

        session.delete(setting)
        logger.info(f"Deleted setting: {key}")
        return True


def init_default_settings():
    """
    初始化默认设置项
    仅在设置不存在时创建，不会覆盖已有设置
    """
    default_settings = [
        # User & Access Control
        {
            "key": "auth_token_expire_hours",
            "value": "168",
            "value_type": "int",
            "category": "auth",
            "description": "用户 Token 过期时间（小时），默认 7 天",
            "is_public": False
        },
        {
            "key": "guest_analysis_limit",
            "value": "3",
            "value_type": "int",
            "category": "limits",
            "description": "访客用户分析次数限制",
            "is_public": True
        },
        # Analysis Behavior
        {
            "key": "cleanup_analysis_files",
            "value": "false",
            "value_type": "bool",
            "category": "analysis",
            "description": "分析完成后是否自动清理临时文件",
            "is_public": False
        },
        {
            "key": "batch_refresh_concurrency",
            "value": "4",
            "value_type": "int",
            "category": "performance",
            "description": "批量刷新库状态的并发线程数",
            "is_public": False
        },
        # Timeouts
        {
            "key": "celery_task_timeout",
            "value": "6000",
            "value_type": "int",
            "category": "performance",
            "description": "Celery 任务超时时间（秒），默认 100 分钟",
            "is_public": False
        },
        {
            "key": "redis_session_ttl",
            "value": "1800",
            "value_type": "int",
            "category": "performance",
            "description": "Redis Session 过期时间（秒），默认 30 分钟",
            "is_public": False
        },
    ]

    with session_generator() as session:
        for setting_data in default_settings:
            existing = session.query(SystemSetting).filter(
                SystemSetting.key == setting_data["key"]
            ).first()

            if existing is None:
                setting = SystemSetting(**setting_data)
                session.add(setting)
                logger.info(f"Initialized default setting: {setting_data['key']}")

        session.commit()

    logger.info("Default settings initialization completed")
