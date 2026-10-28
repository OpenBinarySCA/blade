"""
Settings Service

运行时设置服务，提供带缓存的设置读取和管理功能。
支持从数据库读取设置，并在内存中缓存以提高性能。
"""
import json
import threading
from typing import Any, Optional
from datetime import datetime, timedelta
from loguru import logger

from ...databases.user_data.repository import settings_repository
from ...config import settings as env_settings


class SettingsService:
    """
    运行时设置服务

    特性：
    - 内存缓存，减少数据库查询
    - 支持缓存过期和手动刷新
    - 优雅降级：数据库不可用时使用环境变量默认值
    """

    # 缓存过期时间（秒）
    CACHE_TTL = 300  # 5 minutes

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._initialized = False

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache_timestamps:
            return False
        elapsed = datetime.now() - self._cache_timestamps[key]
        return elapsed < timedelta(seconds=self.CACHE_TTL)

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取值"""
        with self._lock:
            if self._is_cache_valid(key):
                return self._cache.get(key)
        return None

    def _set_cache(self, key: str, value: Any):
        """设置缓存"""
        with self._lock:
            self._cache[key] = value
            self._cache_timestamps[key] = datetime.now()

    def _clear_cache(self, key: Optional[str] = None):
        """清除缓存"""
        with self._lock:
            if key:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            else:
                self._cache.clear()
                self._cache_timestamps.clear()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取设置值

        优先级：
        1. 内存缓存
        2. 数据库
        3. 默认值

        Args:
            key: 设置项键名
            default: 默认值

        Returns:
            设置值
        """
        # 1. 尝试从缓存获取
        cached = self._get_from_cache(key)
        if cached is not None:
            return cached

        # 2. 从数据库获取
        try:
            value = settings_repository.get_setting_value(key)
            if value is not None:
                self._set_cache(key, value)
                return value
        except Exception as e:
            logger.warning(f"Failed to get setting from database: {key}, error: {e}")

        # 3. 返回默认值
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数类型设置"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔类型设置"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return default

    def get_str(self, key: str, default: str = "") -> str:
        """获取字符串类型设置"""
        value = self.get(key, default)
        return str(value) if value is not None else default

    def set(self, key: str, value: Any, value_type: str = "str",
            category: str = "general", description: Optional[str] = None,
            is_public: bool = False):
        """
        设置配置值

        Args:
            key: 设置项键名
            value: 设置值
            value_type: 值类型 (int, bool, str, json)
            category: 分类
            description: 描述
            is_public: 是否公开
        """
        # 转换值为字符串
        if value_type == "bool":
            str_value = "true" if value else "false"
        elif value_type == "json":
            str_value = json.dumps(value)
        else:
            str_value = str(value)

        # 更新数据库
        settings_repository.upsert_setting(
            key=key,
            value=str_value,
            value_type=value_type,
            category=category,
            description=description,
            is_public=is_public
        )

        # 更新缓存
        self._set_cache(key, value)
        logger.info(f"Setting updated: {key} = {value}")

    def refresh(self, key: Optional[str] = None):
        """
        刷新缓存

        Args:
            key: 指定键名刷新单个设置，None 则刷新所有
        """
        self._clear_cache(key)
        logger.info(f"Cache refreshed: {key or 'all'}")

    def get_all(self, category: Optional[str] = None) -> dict[str, Any]:
        """
        获取所有设置

        Args:
            category: 可选，按分类过滤

        Returns:
            设置字典 {key: value}
        """
        try:
            if category:
                settings = settings_repository.get_settings_by_category(category)
            else:
                settings = settings_repository.get_all_settings()

            return {s.key: s.get_typed_value() for s in settings}
        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            return {}

    def get_public_settings(self) -> dict[str, Any]:
        """获取所有公开设置"""
        try:
            settings = settings_repository.get_public_settings()
            return {s.key: s.get_typed_value() for s in settings}
        except Exception as e:
            logger.error(f"Failed to get public settings: {e}")
            return {}

    def init_defaults(self):
        """初始化默认设置"""
        if self._initialized:
            return

        try:
            settings_repository.init_default_settings()
            self._initialized = True
            logger.info("Settings service initialized with defaults")
        except Exception as e:
            logger.error(f"Failed to initialize default settings: {e}")

    # =========================================================================
    # 便捷属性 - 常用设置的快捷访问
    # =========================================================================

    @property
    def guest_analysis_limit(self) -> int:
        """访客分析次数限制"""
        return self.get_int("guest_analysis_limit", env_settings.GUEST_ANALYSIS_LIMIT)

    @property
    def auth_token_expire_hours(self) -> int:
        """Token 过期时间（小时）"""
        return self.get_int("auth_token_expire_hours", env_settings.AUTH_TOKEN_EXPIRE_HOURS)

    @property
    def cleanup_analysis_files(self) -> bool:
        """是否清理分析文件"""
        return self.get_bool("cleanup_analysis_files", env_settings.CLEANUP_ANALYSIS_FILES)

    @property
    def batch_refresh_concurrency(self) -> int:
        """批量刷新并发数"""
        return self.get_int("batch_refresh_concurrency", env_settings.BATCH_REFRESH_CONCURRENCY)


# 全局单例
_settings_service: Optional[SettingsService] = None
_service_lock = threading.Lock()


def get_settings_service() -> SettingsService:
    """获取设置服务单例"""
    global _settings_service
    if _settings_service is None:
        with _service_lock:
            if _settings_service is None:
                _settings_service = SettingsService()
    return _settings_service


# 便捷函数
def get_setting(key: str, default: Any = None) -> Any:
    """获取设置值"""
    return get_settings_service().get(key, default)


def set_setting(key: str, value: Any, **kwargs):
    """设置配置值"""
    return get_settings_service().set(key, value, **kwargs)
