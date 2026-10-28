# log.py
import logging
import logging.config
import sys
from typing import Optional

# ------------------------
# 全局开关：是否启用调试日志
# 默认 False → 只打印 INFO 以上日志
# 改成 True → DEBUG 也会打印
# ------------------------
ENABLE_DEBUG_LOG = False

# ------------------------
# 日志配置
# ------------------------
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': 'DEBUG' if ENABLE_DEBUG_LOG else 'INFO',
            'stream': sys.stdout,
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'standard',
            'level': 'DEBUG',  # 文件里保留完整日志
            'filename': 'extractor.log',
            'mode': 'w',
            'encoding': 'utf-8'
        },
    },
    'loggers': {
        # 根 logger：默认控制台输出
        '': {
            'handlers': ['console'],
            'level': 'DEBUG' if ENABLE_DEBUG_LOG else 'INFO',
            'propagate': True
        },
        # 项目包 logger（比如 engine）：控制台 + 文件
        'engine': {
            'handlers': ['console'],
            'level': 'DEBUG' if ENABLE_DEBUG_LOG else 'INFO',
            'propagate': False
        },
    }
}

logging.config.dictConfig(LOGGING_CONFIG)


def getLogger(name: Optional[str] = None) -> logging.Logger:
    base = "engine"
    full_name = base if not name else f"{base}.{name}"
    return logging.getLogger(full_name)
