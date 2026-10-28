from .celery_app import celery_app
from . import tpl_detection_task

__all__ = ['celery_app', 'tpl_detection_task']
