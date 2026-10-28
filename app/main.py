"""
BSCA Expert Agent API
二进制软件成分分析专家代理API
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import settings
from .api.v1.endpoints.app import (
    tpl_detection_router,
    file_operations_router,
    result_chat_router,
    version_router,
)
from .api.v1.endpoints.admin import data_management_router, settings_router, users_router, tasks_router, system_monitor_router
from .api.v1.endpoints.auth import router as auth_router
from .databases.user_data import init_user_data_schema
from .services.settings import get_settings_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Initializing user_data schema...")
    try:
        init_user_data_schema()
        logger.info("User data schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize user_data schema: {e}")

    # Initialize default settings
    logger.info("Initializing default settings...")
    try:
        get_settings_service().init_defaults()
        logger.info("Default settings initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize default settings: {e}")

    yield

    # Shutdown
    logger.info("Application shutting down...")


def create_app() -> FastAPI:
    """创建FastAPI应用"""

    app = FastAPI(
        title=settings.app_name,
        version=settings.APP_VERSION,
        description="二进制软件成分分析专家代理API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 在生产环境中应该设置具体的域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
    app.include_router(tpl_detection_router, prefix="/api/v1", tags=["TPL Detection"])
    app.include_router(file_operations_router, prefix="/api/v1", tags=["File Operations"])
    app.include_router(result_chat_router, prefix="/api/v1", tags=["Result Chat"])
    app.include_router(data_management_router, prefix="/api/v1", tags=["Data Management"])
    app.include_router(settings_router, prefix="/api/v1/admin", tags=["Admin - Settings"])
    app.include_router(users_router, prefix="/api/v1/admin", tags=["Admin - Users"])
    app.include_router(tasks_router, prefix="/api/v1/admin", tags=["Admin - Tasks"])
    app.include_router(system_monitor_router, prefix="/api/v1/admin", tags=["Admin - System Monitor"])
    app.include_router(version_router, prefix="/api/v1", tags=["Version"])

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )