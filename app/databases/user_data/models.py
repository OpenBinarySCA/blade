"""
User Data Models - user_data schema

应用运行时数据模型，存储在 user_data schema 中，与 TPL 知识库数据分离
包括：用户、OAuth连接、分析任务、访客使用记录、系统设置等
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, create_engine, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, declared_attr
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

from loguru import logger


Base = declarative_base()

# Schema name
SCHEMA_NAME = "user_data"


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=func.now(), nullable=False, server_default=func.now())

    @declared_attr
    def updated_at(cls):
        return Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, server_default=func.now())


class User(TimestampMixin, Base):
    """
    用户表
    User table for authentication and profile storage
    """
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # User profile fields
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Admin flag
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default='false')

    # Relationships
    oauth_connections = relationship("OAuthConnection", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("AnalysisTask", back_populates="user")


class OAuthConnection(TimestampMixin, Base):
    """
    OAuth 连接表
    Stores OAuth provider connections for each user (Google, GitHub, etc.)
    """
    __tablename__ = "oauth_connections"
    __table_args__ = (
        # One user can only link one account per provider
        UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
        # One provider account can only be linked to one user
        UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user_id'),
        {"schema": SCHEMA_NAME}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=False, index=True)

    # OAuth provider info
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'google', 'github', etc.
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Provider's user ID (Google sub)

    # Optional: store tokens for refresh/API access
    access_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_expires_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Store provider-specific profile data as JSON string
    profile_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    user = relationship("User", back_populates="oauth_connections")


class AnalysisTask(TimestampMixin, Base):
    """
    分析任务表
    Stores analysis task records with user association
    """
    __tablename__ = "analysis_tasks"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # User association (nullable = guest)
    user_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA_NAME}.users.id"), nullable=True, index=True)

    # New fields
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Basic info
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_minio_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Status and timing
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    start_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)

    # Results
    result_minio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    report_minio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Statistics
    analysis_total_files: Mapped[int] = mapped_column(default=0)
    analysis_completed_files: Mapped[int] = mapped_column(default=0)

    # Relationship
    user = relationship("User", back_populates="tasks")

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "engine_version": self.engine_version,
            "input_file_sha256": self.input_file_sha256,
            "file_name": self.file_name,
            "file_minio_path": self.file_minio_path,
            "status": self.status,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "result_minio_path": self.result_minio_path,
            "report_minio_path": self.report_minio_path,
            "error_message": self.error_message,
            "analysis_total_files": self.analysis_total_files,
            "analysis_completed_files": self.analysis_completed_files,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GuestUsage(TimestampMixin, Base):
    """
    访客使用记录表
    Tracks guest usage based on IP + device fingerprint
    """
    __tablename__ = "guest_usage"
    __table_args__ = (
        UniqueConstraint('ip_address', 'device_fingerprint', name='uq_guest_device'),
        {"schema": SCHEMA_NAME}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Device identification (IP + User-Agent hash)
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    # Usage count
    usage_count: Mapped[int] = mapped_column(default=1)
    last_used_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)


class SystemSetting(TimestampMixin, Base):
    """
    系统设置表
    存储可在运行时通过管理后台修改的配置项

    设计说明：
    - key: 设置项的唯一标识符，如 "guest_analysis_limit"
    - value: 设置值，统一存储为字符串，由应用层解析类型
    - value_type: 值类型提示 (int, bool, str, json)，用于前端展示和验证
    - category: 分类，用于管理后台分组显示
    - description: 描述，用于管理后台展示
    - is_public: 是否可以通过公开 API 获取（非敏感配置）
    """
    __tablename__ = "system_settings"
    __table_args__ = {"schema": SCHEMA_NAME}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), nullable=False, default="str")  # int, bool, str, json
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "key": self.key,
            "value": self.get_typed_value(),
            "value_type": self.value_type,
            "category": self.category,
            "description": self.description,
            "is_public": self.is_public,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_typed_value(self):
        """根据 value_type 返回正确类型的值"""
        if self.value_type == "int":
            return int(self.value)
        elif self.value_type == "bool":
            return self.value.lower() in ("true", "1", "yes")
        elif self.value_type == "json":
            import json
            return json.loads(self.value)
        else:
            return self.value


def create_user_data_tables(db_url: str, drop_existing: bool = False):
    """
    创建 user_data schema 中的所有表

    Args:
        db_url: PostgreSQL 连接 URL
        drop_existing: 是否先删除现有表（危险操作，仅用于开发）
    """
    engine = create_engine(
        url=db_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )

    # Create schema if not exists
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_NAME}"))
        conn.commit()
        logger.info(f"Schema '{SCHEMA_NAME}' ensured")

    if drop_existing:
        logger.warning(f"Dropping all tables in schema '{SCHEMA_NAME}'...")
        Base.metadata.drop_all(engine)

    # Create all tables
    Base.metadata.create_all(engine)
    logger.info(f"Tables in schema '{SCHEMA_NAME}' created successfully")


if __name__ == '__main__':
    # For testing: create tables in local database
    from ...config import settings
    create_user_data_tables(settings.DATABASE_URL)
