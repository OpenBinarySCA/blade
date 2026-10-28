# BLADE 项目依赖清单

本文档记录了 BLADE 项目所依赖的所有组件及其版本信息。

## 目录
- [Python 环境](#python-环境)
- [核心 Python 依赖](#核心-python-依赖)
- [基础设施服务](#基础设施服务)
- [系统工具和二进制依赖](#系统工具和二进制依赖)
- [开发和部署工具](#开发和部署工具)

---

## Python 环境

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11 | 基础 Python 运行环境 |
| pip | latest | Python 包管理器 |

---

## 核心 Python 依赖

### Web 框架和 API
这些是构建 Web 服务的核心组件。

| 包名 | 版本 | 说明 |
|------|------|------|
| **fastapi** | **0.116.2** | 现代、高性能的 Web 框架，用于构建 API |
| **uvicorn** | **0.35.0** | ASGI 服务器实现，用于运行 FastAPI 应用 |
| pydantic | 2.11.10 | 数据验证和设置管理 |
| pydantic-settings | 2.10.1 | Pydantic 配置管理扩展 |

### 数据库和存储
项目使用多种数据库和存储解决方案。

| 包名 | 版本 | 说明 |
|------|------|------|
| **SQLAlchemy** | **2.0.44** | Python SQL 工具包和 ORM |
| **psycopg2-binary** | **2.9.10** | PostgreSQL 数据库适配器 |
| **pgvector** | **0.4.1** | PostgreSQL 向量扩展的 Python 客户端 |
| **lancedb** | **0.25.2** | 向量数据库，用于 AI 应用的嵌入存储 |
| **minio** | **7.2.18** | MinIO 对象存储 Python SDK |

### 任务队列和缓存
分布式任务处理和数据缓存。

| 包名 | 版本 | 说明 |
|------|------|------|
| **celery** | **5.5.3** | 分布式任务队列系统 |
| **redis** | **6.2.0** | Redis 客户端库，用于缓存和消息代理 |
| schedule | 1.2.2 | 作业调度库 |

### AI 和机器学习
核心 AI 功能依赖的关键组件。

| 包名 | 版本 | 说明 |
|------|------|------|
| **agno** | **2.2.5** | 🔥 Agent 框架，项目的核心 AI Agent 引擎 |
| **openai** | **2.6.1** | OpenAI API 客户端 |
| **anthropic** | **0.72.0** | Anthropic API 客户端 |
| **ollama** | **0.6.0** | Ollama 本地 LLM 客户端 |
| tantivy | 0.25.0 | 全文搜索引擎库 |

### 数据处理和分析

| 包名 | 版本 | 说明 |
|------|------|------|
| networkx | 3.5 | 复杂网络分析库 |
| scipy | 1.16.3 | 科学计算库 |
| matplotlib | 3.10.7 | 数据可视化库 |
| yfinance | 0.2.66 | Yahoo Finance 数据下载器 |

### 网络和 HTTP 请求

| 包名 | 版本 | 说明 |
|------|------|------|
| requests | 2.32.5 | HTTP 库 |
| duckduckgo-search | 9.6.1 | DuckDuckGo 搜索 API |
| ddgs | 9.6.1 | DuckDuckGo 搜索工具 |
| pygithub | 3.1.45 | GitHub API v3 客户端 |

### 版本控制和代码分析

| 包名 | 版本 | 说明 |
|------|------|------|
| GitPython | 3.1.45 | Git 仓库操作库 |
| pylance | 0.38.3 | Python 语言服务器 |

### 二进制分析和逆向工程
用于固件分析和二进制文件处理的核心工具。

| 包名 | 版本 | 说明 |
|------|------|------|
| **lief** | **0.16.7** | 二进制文件解析和修改库 |
| binaryai | 0.2.8 | 二进制代码相似性分析 |
| conan | 2.22.1 | C/C++ 包管理器 |
| r2pipe | 1.9.6 | Radare2 Python 绑定 |

### 工具和实用程序

| 包名 | 版本 | 说明 |
|------|------|------|
| tqdm | 4.67.1 | 进度条库 |
| loguru | 0.7.3 | 简化的日志记录 |
| environs | 14.2.0 | 环境变量解析 |

### 固件解压和文件系统解析
用于固件和各种压缩格式的解析工具。

| 包名 | 版本 | 说明 |
|------|------|------|
| filetype | 1.2.0 | 文件类型检测 |
| chardet | 5.2.0 | 字符编码检测 |
| kaitaistruct | 0.11 | 二进制文件解析 |
| crcmod | 1.7 | CRC 校验 |
| easy_enum | 1.0.6 | 枚举类型简化 |
| liblp | 1.0.2 | Android 逻辑分区处理 |
| zstandard | 0.25.0 | Zstandard 压缩算法 |
| dissect.cstruct | 3.14 | C 结构体解析 |
| dissect.squashfs | 1.5 | SquashFS 文件系统 |
| dissect.util | 3.23.dev9 | Dissect 工具集 |
| dissect.extfs | 3.10 | Ext 文件系统 |
| dissect.fat | 3.9 | FAT 文件系统 |
| dissect.volume | 3.10 | 卷管理 |
| pycdlib | 1.14.0 | ISO 文件处理 |
| cstruct | 6.1 | C 结构体解析 |
| fdt | 0.3.3 | 设备树文件解析 |
| ubi-reader | 0.8.12 | UBI 文件系统解析 |
| python-lzo | 1.15 | LZO 压缩算法 |

---

## 基础设施服务

这些服务通过 Docker Compose 部署和管理。

### PostgreSQL 数据库

| 组件 | 版本 | 说明 |
|------|------|------|
| **PostgreSQL** | **16** | 主数据库系统 |
| 容器镜像 | postgres:16 | 官方 PostgreSQL Docker 镜像 |
| 端口映射 | 5466:5432 | 宿主机端口:容器端口 |
| 数据库名 | tpl_data | 主数据库名称 |
| 用户名 | tpl_data | 数据库用户 |
| 数据持久化 | ./blade_containers_data/postgresql_data | 数据卷挂载路径 |

**扩展：**
- pgvector：用于向量存储和相似度搜索

### Redis 缓存和消息队列

| 组件 | 版本 | 说明 |
|------|------|------|
| **Redis** | **latest** | 内存数据存储 |
| 容器镜像 | redis:latest | 官方 Redis Docker 镜像 |
| 端口映射 | 6366:6379 | 宿主机端口:容器端口 |
| 持久化模式 | AOF | Append Only File 持久化 |
| 数据持久化 | ./blade_containers_data/redis-data | 数据卷挂载路径 |

**数据库分配：**
- DB 0：Celery Broker（任务队列）
- DB 1：Celery Result（结果存储）
- DB 2：Metadata（元数据缓存）

### MinIO 对象存储

| 组件 | 版本 | 说明 |
|------|------|------|
| **MinIO** | **latest** | S3 兼容的对象存储服务 |
| 容器镜像 | minio/minio:latest | 官方 MinIO Docker 镜像 |
| API 端口 | 9000 | MinIO API 服务端口 |
| Console 端口 | 9001 | MinIO Web 控制台端口 |
| 管理员账户 | minioadmin | 默认用户名和密码 |
| 数据持久化 | ./blade_containers_data/minio_data | 数据卷挂载路径 |

**存储桶（Buckets）：**
- input-files：输入文件存储
- output-files：输出文件存储

---

## 系统工具和二进制依赖

这些是在 Docker 容器中安装的系统级工具，用于固件分析和二进制处理。

### 固件分析工具

| 工具 | 版本/来源 | 说明 |
|------|-----------|------|
| **binwalk** | **v2.3.4** | 固件分析和提取工具，从 ReFirmLabs GitHub 安装 |
| **radare2** | **latest** | 逆向工程框架，从官方 GitHub 编译安装 |
| unar | 系统包 | 通用解压工具 |
| squashfs-tools | 系统包 | SquashFS 文件系统工具 |
| unyaffs | 系统包 | YAFFS 文件系统提取工具 |

### 系统库和依赖

| 库 | 说明 |
|------|------|
| liblzo2-dev | LZO 压缩库开发文件 |
| zstd | Zstandard 压缩工具 |
| git | 版本控制系统 |
| build-essential | 编译工具链（gcc, g++, make 等）|
| pkg-config | 包配置工具 |
| libzip-dev | ZIP 库开发文件 |
| curl | HTTP 客户端 |
| liblzma-dev | LZMA 压缩库 |
| zlib1g-dev | zlib 压缩库 |

---

## 开发和部署工具

### Docker 相关

| 组件 | 说明 |
|------|------|
| Docker | 容器化平台 |
| Docker Compose | 多容器编排工具 |
| 基础镜像 | tiangolo/uvicorn-gunicorn:python3.11 |

### 网络配置

| 配置项 | 值 |
|--------|------|
| Docker 网络 | blade-network (bridge) |
| API 服务端口 | 8000:80 |
| 工作空间 | ./blade_containers_data/api_data/workspace |

---

## 版本更新记录

| 日期 | 说明 |
|------|------|
| 2025-01-03 | 初始版本，记录所有依赖的精确版本号 |

---

## 注意事项

1. **Python 依赖管理**：所有 Python 包版本已固定在 `requirements.txt` 中，确保部署环境的一致性。

2. **服务端口冲突**：请确保宿主机上的以下端口未被占用：
   - 5466 (PostgreSQL)
   - 6366 (Redis)
   - 9000, 9001 (MinIO)
   - 8000 (API 服务)

3. **数据持久化**：所有容器数据存储在 `./compose/blade_containers_data/` 目录下，请定期备份。

4. **二进制工具**：binwalk 和 radare2 在容器构建时从源码编译安装，确保使用特定版本。

5. **环境变量**：项目配置通过 `.env` 文件管理，详细配置项请参考 `.env.example`。

6. **LLM 提供商**：支持 OpenAI、Anthropic 和 Ollama，根据需要配置相应的 API 密钥。
