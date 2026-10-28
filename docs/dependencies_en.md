# BLADE Project Dependencies

This document records all components and their version information that the BLADE project depends on.

## Table of Contents
- [Python Environment](#python-environment)
- [Core Python Dependencies](#core-python-dependencies)
- [Infrastructure Services](#infrastructure-services)
- [System Tools and Binary Dependencies](#system-tools-and-binary-dependencies)
- [Development and Deployment Tools](#development-and-deployment-tools)

---

## Python Environment

| Component | Version | Description |
|-----------|---------|-------------|
| Python | 3.11 | Base Python runtime environment |
| pip | latest | Python package manager |

---

## Core Python Dependencies

### Web Framework and API
Core components for building web services.

| Package | Version | Description |
|---------|---------|-------------|
| **fastapi** | **0.116.2** | Modern, high-performance web framework for building APIs |
| **uvicorn** | **0.35.0** | ASGI server implementation for running FastAPI applications |
| pydantic | 2.11.10 | Data validation and settings management |
| pydantic-settings | 2.10.1 | Pydantic configuration management extension |

### Database and Storage
The project uses multiple database and storage solutions.

| Package | Version | Description |
|---------|---------|-------------|
| **SQLAlchemy** | **2.0.44** | Python SQL toolkit and ORM |
| **psycopg2-binary** | **2.9.10** | PostgreSQL database adapter |
| **pgvector** | **0.4.1** | Python client for PostgreSQL vector extension |
| **lancedb** | **0.25.2** | Vector database for AI application embedding storage |
| **minio** | **7.2.18** | MinIO object storage Python SDK |

### Task Queue and Cache
Distributed task processing and data caching.

| Package | Version | Description |
|---------|---------|-------------|
| **celery** | **5.5.3** | Distributed task queue system |
| **redis** | **6.2.0** | Redis client library for caching and message broker |
| schedule | 1.2.2 | Job scheduling library |

### AI and Machine Learning
Key components for core AI functionality.

| Package | Version | Description |
|---------|---------|-------------|
| **agno** | **2.2.5** | 🔥 Agent framework, the core AI Agent engine of the project |
| **openai** | **2.6.1** | OpenAI API client |
| **anthropic** | **0.72.0** | Anthropic API client |
| **ollama** | **0.6.0** | Ollama local LLM client |
| tantivy | 0.25.0 | Full-text search engine library |

### Data Processing and Analysis

| Package | Version | Description |
|---------|---------|-------------|
| networkx | 3.5 | Complex network analysis library |
| scipy | 1.16.3 | Scientific computing library |
| matplotlib | 3.10.7 | Data visualization library |
| yfinance | 0.2.66 | Yahoo Finance data downloader |

### Network and HTTP Requests

| Package | Version | Description |
|---------|---------|-------------|
| requests | 2.32.5 | HTTP library |
| duckduckgo-search | 9.6.1 | DuckDuckGo search API |
| ddgs | 9.6.1 | DuckDuckGo search tool |
| pygithub | 3.1.45 | GitHub API v3 client |

### Version Control and Code Analysis

| Package | Version | Description |
|---------|---------|-------------|
| GitPython | 3.1.45 | Git repository operations library |
| pylance | 0.38.3 | Python language server |

### Binary Analysis and Reverse Engineering
Core tools for firmware analysis and binary file processing.

| Package | Version | Description |
|---------|---------|-------------|
| **lief** | **0.16.7** | Binary file parsing and modification library |
| binaryai | 0.2.8 | Binary code similarity analysis |
| conan | 2.22.1 | C/C++ package manager |
| r2pipe | 1.9.6 | Radare2 Python bindings |

### Tools and Utilities

| Package | Version | Description |
|---------|---------|-------------|
| tqdm | 4.67.1 | Progress bar library |
| loguru | 0.7.3 | Simplified logging |
| environs | 14.2.0 | Environment variable parsing |

### Firmware Extraction and File System Parsing
Tools for parsing firmware and various compression formats.

| Package | Version | Description |
|---------|---------|-------------|
| filetype | 1.2.0 | File type detection |
| chardet | 5.2.0 | Character encoding detection |
| kaitaistruct | 0.11 | Binary file parsing |
| crcmod | 1.7 | CRC checksum |
| easy_enum | 1.0.6 | Enum type simplification |
| liblp | 1.0.2 | Android logical partition processing |
| zstandard | 0.25.0 | Zstandard compression algorithm |
| dissect.cstruct | 3.14 | C structure parsing |
| dissect.squashfs | 1.5 | SquashFS file system |
| dissect.util | 3.23.dev9 | Dissect toolset |
| dissect.extfs | 3.10 | Ext file system |
| dissect.fat | 3.9 | FAT file system |
| dissect.volume | 3.10 | Volume management |
| pycdlib | 1.14.0 | ISO file processing |
| cstruct | 6.1 | C structure parsing |
| fdt | 0.3.3 | Device tree file parsing |
| ubi-reader | 0.8.12 | UBI file system parsing |
| python-lzo | 1.15 | LZO compression algorithm |

---

## Infrastructure Services

These services are deployed and managed via Docker Compose.

### PostgreSQL Database

| Component | Version | Description |
|-----------|---------|-------------|
| **PostgreSQL** | **16** | Primary database system |
| Container Image | postgres:16 | Official PostgreSQL Docker image |
| Port Mapping | 5466:5432 | Host port:Container port |
| Database Name | tpl_data | Main database name |
| Username | tpl_data | Database user |
| Data Persistence | ./blade_containers_data/postgresql_data | Data volume mount path |

**Extensions:**
- pgvector: For vector storage and similarity search

### Redis Cache and Message Queue

| Component | Version | Description |
|-----------|---------|-------------|
| **Redis** | **latest** | In-memory data store |
| Container Image | redis:latest | Official Redis Docker image |
| Port Mapping | 6366:6379 | Host port:Container port |
| Persistence Mode | AOF | Append Only File persistence |
| Data Persistence | ./blade_containers_data/redis-data | Data volume mount path |

**Database Allocation:**
- DB 0: Celery Broker (task queue)
- DB 1: Celery Result (result storage)
- DB 2: Metadata (metadata cache)

### MinIO Object Storage

| Component | Version | Description |
|-----------|---------|-------------|
| **MinIO** | **latest** | S3-compatible object storage service |
| Container Image | minio/minio:latest | Official MinIO Docker image |
| API Port | 9000 | MinIO API service port |
| Console Port | 9001 | MinIO web console port |
| Admin Account | minioadmin | Default username and password |
| Data Persistence | ./blade_containers_data/minio_data | Data volume mount path |

**Buckets:**
- input-files: Input file storage
- output-files: Output file storage

---

## System Tools and Binary Dependencies

These are system-level tools installed in Docker containers for firmware analysis and binary processing.

### Firmware Analysis Tools

| Tool | Version/Source | Description |
|------|----------------|-------------|
| **binwalk** | **v2.3.4** | Firmware analysis and extraction tool, installed from ReFirmLabs GitHub |
| **radare2** | **latest** | Reverse engineering framework, compiled from official GitHub |
| unar | System package | Universal decompression tool |
| squashfs-tools | System package | SquashFS file system tools |
| unyaffs | System package | YAFFS file system extraction tool |

### System Libraries and Dependencies

| Library | Description |
|---------|-------------|
| liblzo2-dev | LZO compression library development files |
| zstd | Zstandard compression tool |
| git | Version control system |
| build-essential | Compilation toolchain (gcc, g++, make, etc.) |
| pkg-config | Package configuration tool |
| libzip-dev | ZIP library development files |
| curl | HTTP client |
| liblzma-dev | LZMA compression library |
| zlib1g-dev | zlib compression library |

---

## Development and Deployment Tools

### Docker Related

| Component | Description |
|-----------|-------------|
| Docker | Container platform |
| Docker Compose | Multi-container orchestration tool |
| Base Image | tiangolo/uvicorn-gunicorn:python3.11 |

### Network Configuration

| Configuration | Value |
|---------------|-------|
| Docker Network | blade-network (bridge) |
| API Service Port | 8000:80 |
| Workspace | ./blade_containers_data/api_data/workspace |

---

## Version Update Log

| Date | Description |
|------|-------------|
| 2025-01-03 | Initial version, recording exact versions of all dependencies |

---

## Notes

1. **Python Dependency Management**: All Python package versions are pinned in `requirements.txt` to ensure consistency across deployment environments.

2. **Service Port Conflicts**: Please ensure the following ports on the host machine are not occupied:
   - 5466 (PostgreSQL)
   - 6366 (Redis)
   - 9000, 9001 (MinIO)
   - 8000 (API Service)

3. **Data Persistence**: All container data is stored in the `./compose/blade_containers_data/` directory. Please backup regularly.

4. **Binary Tools**: binwalk and radare2 are compiled and installed from source code during container build to ensure specific versions are used.

5. **Environment Variables**: Project configuration is managed through the `.env` file. For detailed configuration items, please refer to `.env.example`.

6. **LLM Providers**: Supports OpenAI, Anthropic, and Ollama. Configure the corresponding API keys as needed.
