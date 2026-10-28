"""
Application Configuration

配置分为两类：
1. Environment Config (环境配置): 启动前必须设置，来自环境变量，运行时不可修改
2. Runtime Settings (运行时设置): 可通过管理后台修改，存储在数据库中

当前所有配置都从环境变量读取。
未来计划：Runtime Settings 部分将支持从数据库读取，允许在管理后台动态修改。
"""
from pydantic_settings import BaseSettings
from environs import Env

env = Env()
env.read_env()


class Settings(BaseSettings):
    # =========================================================================
    # ENVIRONMENT CONFIG (环境配置 - 启动前设置，运行时不可修改)
    # =========================================================================

    # ----- Application -----
    app_name: str = env.str("APP_NAME", "BLADE")
    host: str = env.str("APP_HOST", "0.0.0.0")
    port: int = env.int("APP_PORT", 2000)
    debug: bool = env.bool("APP_DEBUG", False)

    # Version Info
    APP_VERSION: str = env.str("APP_VERSION", "3.1.0")
    ENGINE_VERSION: str = env.str("ENGINE_VERSION", "3.1.0")
    RELEASE_DATETIME: str = env.str("RELEASE_DATETIME", "2025.12.18")

    # ----- Database (PostgreSQL) -----
    # Single database with multiple schemas:
    #   - public schema: TPL knowledge base
    #   - user_data schema: user data
    POSTGRES_HOST: str = env.str("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = env.int("POSTGRES_PORT", 5432)
    POSTGRES_USERNAME: str = env.str("POSTGRES_USERNAME", "blade")
    POSTGRES_PASSWORD: str = env.str("POSTGRES_PASSWORD", "blade")
    POSTGRES_DATABASE: str = env.str("POSTGRES_DATABASE", "blade")

    DATABASE_URL: str = f"postgresql+psycopg2://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"

    # ----- Redis -----
    REDIS_HOST: str = env.str("REDIS_HOST", "blade-redis")
    REDIS_PORT: int = env.int("REDIS_PORT", 6379)
    REDIS_PASSWORD: str = env.str("REDIS_PASSWORD", "")
    REDIS_DB_BROKER: int = env.int("REDIS_DB_BROKER", 0)
    REDIS_DB_RESULT: int = env.int("REDIS_DB_RESULT", 0)
    REDIS_DB_METADATA: int = env.int("REDIS_DB_METADATA", 2)

    @property
    def REDIS_BROKER_URL(self) -> str:
        """Celery broker URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_BROKER}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_BROKER}"

    @property
    def REDIS_RESULT_BACKEND_URL(self) -> str:
        """Celery result backend URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_RESULT}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB_RESULT}"

    # ----- MinIO (Object Storage) -----
    MINIO_ENDPOINT: str = env.str("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = env.str("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY: str = env.str("MINIO_SECRET_KEY", "")
    MINIO_SECURE: bool = env.bool("MINIO_SECURE", False)
    MINIO_INPUT_BUCKET: str = env.str("MINIO_INPUT_BUCKET", "input-files")
    MINIO_OUTPUT_BUCKET: str = env.str("MINIO_OUTPUT_BUCKET", "output-files")
    LOCAL_WORKSPACE_DIR: str = env.str("LOCAL_WORKSPACE_DIR", "/tmp/workspace")

    # ----- Authentication Secrets -----
    AUTH_SECRET: str = env.str("AUTH_SECRET", "blade_secret_key_change_me")
    GOOGLE_CLIENT_ID: str = env.str("GOOGLE_CLIENT_ID", "")
    _ADMIN_EMAILS_STR: str = env.str("ADMIN_EMAILS", "")

    @property
    def ADMIN_EMAILS(self) -> list:
        """Parse comma-separated admin emails"""
        if not self._ADMIN_EMAILS_STR:
            return []
        return [e.strip() for e in self._ADMIN_EMAILS_STR.split(",") if e.strip()]

    # ----- LLM API Keys -----
    LLM_PROVIDER: str = env.str("LLM_PROVIDER", "openai")  # openai, anthropic, ollama, openrouter
    LLM_MODEL_ID: str = env.str("LLM_MODEL_ID", "gpt-4.1")
    OPENAI_API_KEY: str = env.str("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = env.str("ANTHROPIC_API_KEY", "")
    OPENROUTER_API_KEY: str = env.str("OPENROUTER_API_KEY", "")
    OLLAMA_BASE_URL: str = env.str("OLLAMA_BASE_URL", "http://localhost:11434")

    # ----- LLM Pricing (per 1M tokens) -----
    LLM_INPUT_TOKEN_PRICE: float = env.float("LLM_INPUT_TOKEN_PRICE", 2.0)
    LLM_OUTPUT_TOKEN_PRICE: float = env.float("LLM_OUTPUT_TOKEN_PRICE", 8.0)
    LLM_CACHED_INPUT_TOKEN_PRICE: float = env.float("LLM_CACHED_INPUT_TOKEN_PRICE", 0.5)  # 缓存输入价格

    # =========================================================================
    # RUNTIME SETTINGS (运行时设置 - 可通过管理后台修改)
    # 注意：这些设置未来可以迁移到数据库，支持动态修改
    # =========================================================================

    # ----- User & Access Control -----
    AUTH_TOKEN_EXPIRE_HOURS: int = env.int("AUTH_TOKEN_EXPIRE_HOURS", 168)  # 7 days
    GUEST_ANALYSIS_LIMIT: int = env.int("GUEST_ANALYSIS_LIMIT", 10)

    # ----- Analysis Behavior -----
    CLEANUP_ANALYSIS_FILES: bool = env.bool("CLEANUP_ANALYSIS_FILES", False)
    BATCH_REFRESH_CONCURRENCY: int = env.int("BATCH_REFRESH_CONCURRENCY", 4)
    # 直接识别：允许报告召回候选之外、但 Identity Markers 明确揭示的库（生产默认开启；
    # 论文严格模式为 False，见 issta2026 分支）
    ALLOW_DIRECT_DISCOVERY: bool = env.bool("ALLOW_DIRECT_DISCOVERY", True)

    # ----- Timeouts (seconds) -----
    # 未来可添加更多可配置的超时参数
    # CELERY_TASK_TIMEOUT: int = env.int("CELERY_TASK_TIMEOUT", 6000)
    # REDIS_SESSION_TTL: int = env.int("REDIS_SESSION_TTL", 1800)


# Global settings instance
settings = Settings()
