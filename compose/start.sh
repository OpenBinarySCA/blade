#!/bin/bash

# 启动 Gunicorn/Uvicorn (后台运行)
/start.sh &

# 启动 Celery
celery -A app.celery_tasks.celery_app worker --loglevel=info --concurrency=10 -Q tpl_detection_tasks