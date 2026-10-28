import redis

from ...config import settings

# 连接 Redis 用于存储任务元数据
tpl_detection_task_redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
    db=settings.REDIS_DB_METADATA
)

# 连接 Redis 用于存储结果聊天会话
result_chat_redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
    db=settings.REDIS_DB_METADATA  # 使用相同的 DB，通过 key 前缀区分
)

# 连接 Redis 用于存储批量刷新任务元数据
batch_refresh_task_redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
    db=settings.REDIS_DB_METADATA  # 使用相同的 DB，通过 key 前缀 "batch_refresh_task:" 区分
)