"""
Application Constants

存放程序中使用的常量值，这些值不应该被硬编码在代码中。
注意：这里的常量是程序逻辑固定的值，不是用户可配置的设置。
可配置的设置应该放在 config.py (环境配置) 或数据库 (运行时设置) 中。
"""


# =============================================================================
# Task Status Constants
# =============================================================================
class TaskStatus:
    """分析任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# Redis Key Prefixes
# =============================================================================
class RedisKeyPrefix:
    """Redis 键前缀，避免键名冲突"""
    RESULT_CHAT_SESSION = "result_chat:session:"
    TASK_METADATA = "task:metadata:"
    BATCH_REFRESH = "batch_refresh:"


# =============================================================================
# Database Connection Pool Defaults
# =============================================================================
class DBPoolDefaults:
    """数据库连接池默认配置"""
    # Main database
    MAIN_POOL_SIZE = 20
    MAIN_MAX_OVERFLOW = -1  # -1 means unlimited
    MAIN_POOL_RECYCLE = 3600  # 1 hour

    # User data database
    USERDATA_POOL_SIZE = 10
    USERDATA_MAX_OVERFLOW = 20
    USERDATA_POOL_RECYCLE = 3600


# =============================================================================
# Pagination Defaults
# =============================================================================
class PaginationDefaults:
    """分页默认值"""
    LIBRARIES_PAGE_SIZE = 20
    SOURCE_CODE_PAGE_SIZE = 50
    TASKS_PAGE_SIZE = 50
    EVIDENCE_DISPLAY_LIMIT = 20


# =============================================================================
# Timeout Constants (in seconds)
# =============================================================================
class TimeoutSeconds:
    """超时时间常量（秒）"""
    SUBPROCESS_DEFAULT = 300  # 5 minutes
    CELERY_TASK_SOFT_LIMIT = 6000  # 100 minutes
    CELERY_TASK_HARD_LIMIT = 6000  # 100 minutes
    REDIS_SESSION_TTL = 1800  # 30 minutes


# =============================================================================
# Feature Matching Defaults
# =============================================================================
class FeatureMatchingDefaults:
    """特征匹配默认参数（可被 config 覆盖）"""
    MIN_STRING_LENGTH = 5
    MAX_STRING_LENGTH = 500
    MIN_MATCH_NUM = 5
    TOP_N = 10
    MIN_EFFECTIVE_STRING_LENGTH = 10  # 用于过滤的最小有效字符串长度


# =============================================================================
# LLM Tool Limits
# =============================================================================
class LLMToolLimits:
    """LLM 工具调用限制"""
    MAX_TOOL_CALLS = 10
    LIBRARIES_PER_BATCH = 10


# =============================================================================
# File Size Limits
# =============================================================================
class FileSizeLimits:
    """文件大小限制"""
    MAX_UPLOAD_SIZE_MB = 500
    MAX_BINARY_SIZE_MB = 100


# =============================================================================
# OAuth Providers
# =============================================================================
class OAuthProvider:
    """支持的 OAuth 提供商"""
    GOOGLE = "google"
    GITHUB = "github"  # 预留


# =============================================================================
# Confidence Levels
# =============================================================================
class ConfidenceLevel:
    """置信度级别阈值"""
    HIGH = 0.8
    MEDIUM = 0.5
    LOW = 0.3
