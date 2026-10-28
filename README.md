# BLADE - Binary SCA Expert Agent API

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/OpenBinarySCA/blade)
[![License](https://img.shields.io/badge/license-Academic%2FNon--Commercial-green.svg)](#license)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

> **Binary Software Composition Analysis (SCA) Enhanced by AI Agents**

A sophisticated tool for detecting and analyzing Third-Party Libraries (TPLs) in C/C++ compiled binaries without requiring source code access. This project combines AI agents (LLM-powered) with traditional binary analysis techniques to achieve accurate library identification, version detection, and component analysis.

[Report Issues](https://github.com/OpenBinarySCA/blade/issues)

> **ISSTA 2026 paper.** The code and results of *Beyond Similarity Scores: Evidence-Based
> Third-Party Library Detection for C/C++ Binaries* (Proc. ACM Softw. Eng. 3, ISSTA, 2026,
> [doi:10.1145/3832125](https://doi.org/10.1145/3832125)) are on the frozen
> [`issta2026`](https://github.com/OpenBinarySCA/blade/tree/issta2026) branch — see its
> [REPRODUCE.md](https://github.com/OpenBinarySCA/blade/blob/issta2026/REPRODUCE.md).
> `main` is the ongoing development line.

---

## Table of Contents

- [What is Binary SCA?](#what-is-binary-sca)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Usage](#usage)
  - [Python Usage](#python-usage)
  - [API Usage](#api-usage)
- [API Reference](#api-reference)
- [Contributing](#contributing)
- [Citation](#citation)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## What is Binary SCA?

**Binary Software Composition Analysis (SCA)** is a technique for identifying and analyzing third-party libraries and open-source components embedded in compiled binary files, without requiring access to source code.

This project addresses three core questions:
1. **What is this binary?** Is it compiled from a known open-source library?
2. **What static dependencies does it have?** Which third-party libraries are compiled/statically linked into the binary?
3. **What dynamic dependencies does it have?** Which shared libraries does it depend on at runtime?

For a comprehensive explanation of Binary SCA concepts, see [What is Binary SCA?](docs/WhatIsBinarySCA_en.md)

---

## Key Features

### 🤖 Agent-Enhanced Detection
- **AI-powered analysis**: Leverages LLMs (OpenAI, Anthropic, Ollama) to enhance detection accuracy
- **Multi-agent workflow**: Specialized agents for context analysis, TPL detection, version identification, and false positive filtering
- **Evidence-based reasoning**: Combines multiple evidence sources for robust identification

### 🔍 Comprehensive Analysis
- **Library identification**: Detects third-party libraries embedded in binaries
- **Version detection**: Identifies specific library versions through signature analysis
- **Component analysis**: Determines which specific components (e.g., `libssl` vs `libcrypto` in OpenSSL) are used
- **Dependency mapping**: Analyzes both static and dynamic dependencies

### 📦 Multi-Format Support
- **Binary formats**: ELF, PE, Mach-O, and more (via LIEF)
- **Archive formats**: ZIP, TAR, GZIP, BZIP2, XZ, ISO
- **Firmware & embedded systems**: Android images (system.img, vendor.img), Linux filesystems (ext2/3/4, squashfs, fatfs)
- **Mobile platforms**: APK packages and Android native libraries

### 🎯 Advanced Capabilities
- **False positive filtering**: Dedicated agent to refine results and reduce noise
- **Batch processing**: Analyze multiple binaries in parallel
- **Evidence collection**: Multiple extraction methods including string/symbol analysis, binary metadata, and feature matching
- **RESTful API**: Asynchronous task-based API for integration
- **CLI interface**: Command-line tool for standalone usage

### 🔧 Flexible Configuration
- **Multiple LLM providers**: OpenAI, Anthropic, Ollama (local LLMs)
- **Customizable workflows**: Enable/disable specific analysis stages
- **Knowledge base driven**: Uses metadata repositories for accurate library identification
- **Scalable architecture**: Celery-based distributed task queue for handling large workloads

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Client Layer                             │
│              (CLI / REST API / Web UI)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  API Layer (FastAPI)                        │
│          • Task Management  • Authentication                │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│             Task Queue (Celery + Redis)                     │
│               • Async Processing  • Result Cache            │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Detection Workflow Layer                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. Evidence Collection                              │   │
│  │     • Binary Preprocessing  • Metadata Extraction    │   │
│  │     • String/Symbol Analysis  • Feature Matching     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  2. Agent Analysis (LLM-Powered)                     │   │
│  │     • Context Analyzer  • TPL Analyzer               │   │
│  │     • Version Detector  • Result Refiner             │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  3. False Positive Filtering                         │   │
│  │     • Evidence Validation  • Confidence Scoring      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  Data Layer                                 │
│   • PostgreSQL (Metadata, Results)                          │
│   • Redis (Cache, Task Broker)                              │
│   • MinIO (Binary Storage)                                  │
│   • LanceDB (Vector Database for Feature Matching)          │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend Framework**
- FastAPI 0.116+ - High-performance async web framework
- Uvicorn - ASGI server
- Pydantic 2.x - Data validation

**Task Queue & Caching**
- Celery 5.5+ - Distributed task queue
- Redis - Message broker, caching, metadata storage

**Database**
- PostgreSQL + pgvector - Main database with vector search
- SQLAlchemy 2.0 - ORM
- LanceDB - Vector database for feature matching

**AI/LLM Integration**
- agno 2.2.5 - AI agent framework
- OpenAI API - GPT models
- Anthropic API
- Ollama - Local LLM support

**Binary Analysis**
- LIEF 0.16.6 - Binary parsing (ELF, PE, Mach-O)
- r2pipe - Radare2 integration for reverse engineering
- BinaryAI - Binary similarity analysis
- Custom extraction engine - Firmware/filesystem extraction (squashfs, extfs, fatfs, etc.)

**Data Processing**
- NetworkX - Graph analysis for dependency mapping
- SciPy - Scientific computing
- NumPy - Numerical operations

**Storage**
- MinIO - Object storage for binaries and results

---

## Quick Start

### Prerequisites

- **Docker & Docker Compose** - Container platform
  - Install: https://docs.docker.com/get-docker/
  - Verify: `docker --version` and `docker compose version`

- **Python 3.12+** - Required for debug mode
  - Install: https://www.python.org/downloads/
  - Verify: `python3 --version`

- **Node.js** - Required for debug mode frontend
  - Install: https://nodejs.org/
  - Verify: `node --version`

- **LLM API Key** - Required for AI-powered analysis
  - OpenAI: https://platform.openai.com/api-keys
  - OR Anthropic: https://console.anthropic.com/
  - OR Ollama (local): https://ollama.ai/

- **Database Backup** - TPL metadata database (~1.12GB)
  - Download: [database_backup.zip](https://drive.google.com/file/d/1_EuFJoyulFqtABpRTNC30IgrR6sjyXHU/view?usp=sharing)

---

### Production Deployment

Full containerized deployment with Nginx reverse proxy.

```bash
# 1. Clone repository
git clone https://github.com/OpenBinarySCA/blade.git
cd blade

# 2. Configure environment
cp compose/.env.production.example .env
# Edit .env and set your LLM API keys

# 3. Deploy infrastructure (PostgreSQL, Redis, MinIO)
./scripts/deploy_prod_infra.sh

# 4. Restore database (first time only)
unzip database_backup.zip
./scripts/restore_tpl_data.sh --prod tpl_data_backup_*.sql

# 5. Start application (API, Celery, Web, Nginx)
./scripts/start_prod_app.sh
```

**Access:**
- Web UI: http://localhost
- API Docs: http://localhost/api/docs

---

### Debug/Development Mode

Infrastructure in containers, application runs locally for easy development.

```bash
# 1. Clone repository
git clone https://github.com/OpenBinarySCA/blade.git
cd blade

# 2. Configure environment
cp .env.example .env
# Edit .env and set your LLM API keys

# 3. Deploy infrastructure (with exposed ports)
./scripts/deploy_debug_infra.sh

# 4. Restore database (first time only)
unzip database_backup.zip
./scripts/restore_tpl_data.sh --debug tpl_data_backup_*.sql

# 5. Setup Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 6. Install frontend dependencies
cd web && npm install && cd ..

# 7. Start application locally
./scripts/start_debug.sh
```

**Exposed Ports (Debug Mode):**
- PostgreSQL: `localhost:5466`
- Redis: `localhost:6366`
- MinIO API: `localhost:9000`
- MinIO Console: `localhost:9001`

---

### Scripts Reference

| Script | Description |
|--------|-------------|
| `./scripts/deploy_prod_infra.sh` | Start production infrastructure containers |
| `./scripts/deploy_debug_infra.sh` | Start debug infrastructure containers (ports exposed) |
| `./scripts/start_prod_app.sh` | Start production application containers |
| `./scripts/start_debug.sh` | Start application locally (API, Celery, Web) |
| `./scripts/restore_tpl_data.sh --prod <file>` | Restore database to production container |
| `./scripts/restore_tpl_data.sh --debug <file>` | Restore database to debug container |
| `./scripts/backup_tpl_data.sh [path]` | Backup database |

---

### Configuration

**Debug Mode** (`.env`):
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5466
REDIS_HOST=localhost
REDIS_PORT=6366
MINIO_ENDPOINT=localhost:9000

LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

**Production Mode** (`.env`):
```bash
POSTGRES_HOST=blade_postgresql_prod
POSTGRES_PORT=5432
REDIS_HOST=blade_redis_prod
REDIS_PORT=6379
MINIO_ENDPOINT=blade_minio_prod:9000

LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

For complete options, see [.env.example](.env.example) and [compose/.env.production.example](compose/.env.production.example)

### Performance Tuning

| Configuration | Default Value | File Location | Description |
|---------------|---------------|---------------|-------------|
| Celery worker concurrency | 4 (debug) / 10 (prod) | `scripts/start_debug.sh` / `compose/start.sh` | Number of concurrent Celery workers |
| Celery task soft timeout | 6000s | `app/celery_tasks/celery_app.py:19` | Task timeout before `SoftTimeLimitExceeded` |
| Thread pool concurrency | 4 | `app/celery_tasks/tpl_detection_task.py:318` | Threads per task for parallel file analysis |
| Single file analysis timeout | 300s | `app/services/tpl_detection/batch_workflow.py:69` | Timeout for analyzing one binary |

**Total max concurrent analyses** = Celery workers × Thread pool = 4 × 4 = **16 files** (debug mode)

---

## Usage

### Python Usage

Run the detection pipeline directly from Python (needs the TPL database and an LLM API key in `.env`):

```bash
python examples/analyze_single_binary.py          # analyze one binary
python examples/analyze_multiple_binaries.py      # analyze several binaries
python examples/extract_binaries_from_archive_or_firmware.py   # unpack an archive / firmware image first
```

The core entry point is `DetectionWorkflow` in `app/services/tpl_detection/workflow.py`.

---

### API Usage

The API provides a RESTful interface for integration with other systems.

**Starting the API Server**

```bash
python start_server.py
```

The API will be available at `http://localhost:8000`. Interactive documentation is at `http://localhost:8000/docs`.

---

## API Reference

### Create Detection Task

**Endpoint**: `POST /api/v1/tpl_detection_task`

Creates a new TPL detection task for a binary file stored in MinIO.

**Request Body** (JSON):

```json
{
  "file_minio_path": "openssl"
}
```

**Parameters**:
- `file_minio_path` (string, required): Path to the binary file in MinIO input bucket

**Response** (JSON):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "created_at": "2025-01-15T10:30:45.123Z"
}
```

**Example**:

```bash
curl -X POST "http://localhost:8000/api/v1/tpl_detection_task" \
  -H "Content-Type: application/json" \
  -d '{"file_minio_path": "binaries/libssl.so"}'
```

---

### Get Task Status

**Endpoint**: `GET /api/v1/tpl_detection_task`

Retrieves the status and results of a detection task.

**Query Parameters**:
- `task_id` (string, required): The task ID returned from task creation

**Response** (JSON):

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "result": {
    "identified_libraries": [
      {
        "library_name": "OpenSSL",
        "version": "1.1.1k",
        "components": ["libssl"],
        "confidence": 0.95
      }
    ]
  },
  "created_at": "2025-01-15T10:30:45.123Z",
  "completed_at": "2025-01-15T10:31:02.456Z"
}
```

**Task Status Values**:
- `PENDING`: Task is queued
- `STARTED`: Task is processing
- `SUCCESS`: Task completed successfully
- `FAILURE`: Task failed
- `RETRY`: Task is being retried

**Example**:

```bash
curl -X GET "http://localhost:8000/api/v1/tpl_detection_task?task_id=550e8400-e29b-41d4-a716-446655440000"
```

---

## Contributing

We welcome contributions from the community! Here's how you can help:

### How to Contribute

1. **Fork the repository** and clone it locally
2. **Create a new branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** and ensure they follow the code style
4. **Test your changes** thoroughly
5. **Commit your changes** with clear, descriptive messages:
   ```bash
   git commit -m "Add: feature description"
   ```
6. **Push to your fork** and submit a pull request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/blade.git
cd blade

# Install dependencies
pip install -r requirements.txt
```

### Guidelines

- Follow PEP 8 style guidelines for Python code
- Write clear commit messages
- Add tests for new features
- Update documentation as needed
- Be respectful and constructive in discussions

### Reporting Issues

Found a bug or have a feature request? Please [open an issue](https://github.com/OpenBinarySCA/blade/issues) with:
- Clear description of the problem/feature
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

---

## Citation

If you use BLADE in your research, please cite our ISSTA 2026 paper (code and results: branch [`issta2026`](https://github.com/OpenBinarySCA/blade/tree/issta2026)):

```bibtex
@article{liu2026blade,
  title   = {Beyond Similarity Scores: Evidence-Based Third-Party Library Detection for C/C++ Binaries},
  author  = {Liu, Chengyue and Xu, Zhengzi and Zhang, Lyuye and Wu, Jiahui and Li, Kaixuan and Liu, Yang},
  journal = {Proceedings of the ACM on Software Engineering},
  volume  = {3},
  number  = {ISSTA},
  articleno = {ISSTA034},
  year    = {2026},
  doi     = {10.1145/3832125}
}
```

---

## License

This project is licensed under the **[PolyForm Noncommercial License 1.0.0](LICENSE)**.

**Permitted Uses**:
- ✅ Academic research and education
- ✅ Personal learning and experimentation
- ✅ Non-profit organization use
- ✅ Evaluation and testing

**Restricted Uses**:
- ❌ Commercial use without permission
- ❌ Integration into commercial products
- ❌ Providing commercial services based on this software

**Commercial Licensing**: For commercial use, please contact the maintainers by [opening an issue](https://github.com/OpenBinarySCA/blade/issues).

For the full license terms, see [LICENSE](LICENSE).

Copyright © 2025-2026 The BLADE Authors.

---

## Acknowledgments

This project builds upon and integrates several excellent open-source projects:

- **[LIEF](https://lief-project.github.io/)** - Binary parsing and manipulation
- **[Radare2](https://rada.re/)** - Reverse engineering framework
- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern web framework
- **[Celery](https://docs.celeryproject.org/)** - Distributed task queue
- **[agno](https://github.com/agno-agi/agno)** - AI agent framework

Special thanks to the open-source community for their invaluable contributions.

---

**Questions?** Open an [issue](https://github.com/OpenBinarySCA/blade/issues) or check the [documentation](docs/).
