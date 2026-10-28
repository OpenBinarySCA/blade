#!/usr/bin/env python3
"""
BSCA Expert Agent API 启动脚本
二进制软件成分分析专家代理API启动脚本
"""

import os
import sys
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入应用
from app.main import app
from app.config import settings


def main():
    """启动FastAPI服务器"""
    print("🚀 启动 BSCA Expert Agent API...")
    print(f"📝 应用名称: {settings.app_name}")
    print(f"📋 版本: {settings.APP_VERSION}")
    print(f"🌐 主机: {settings.host}")
    print(f"🔌 端口: {settings.port}")
    print(f"🐛 调试模式: {settings.debug}")
    print(f"📚 API文档: http://{settings.host}:{settings.port}/docs")
    print(f"📖 ReDoc文档: http://{settings.host}:{settings.port}/redoc")
    print("-" * 50)

    # 启动服务器
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )


if __name__ == "__main__":
    main() 