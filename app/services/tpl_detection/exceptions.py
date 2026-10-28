"""
BLADE 自定义异常

统一的异常层次结构，便于错误处理和日志记录。
"""


class BladeError(Exception):
    """BLADE 基础异常类"""

    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# ==================== Phase 1: 信息准备异常 ====================

class BinaryParseError(BladeError):
    """二进制解析错误"""
    pass


class FileAccessError(BladeError):
    """文件访问错误（不存在、权限等）"""
    pass


class StringExtractionError(BladeError):
    """字符串提取错误"""
    pass


class SymbolExtractionError(BladeError):
    """符号提取错误"""
    pass


class FeatureMatchingError(BladeError):
    """特征匹配错误"""
    pass


# ==================== Phase 2/3: LLM 分析异常 ====================

class LLMAnalysisError(BladeError):
    """LLM 分析错误基类"""
    pass


class Phase2AnalysisError(LLMAnalysisError):
    """Phase 2（主程序+动态库）分析错误"""
    pass


class Phase3AnalysisError(LLMAnalysisError):
    """Phase 3（静态库）分析错误"""
    pass


class ModelCreationError(BladeError):
    """模型创建错误"""
    pass


class PromptBuildError(BladeError):
    """Prompt 构建错误"""
    pass


# ==================== Phase 4: 版本分析异常 ====================

class VersionAnalysisError(BladeError):
    """版本分析错误"""
    pass


# ==================== 工作流异常 ====================

class WorkflowError(BladeError):
    """工作流错误"""
    pass


class TimeoutError(BladeError):
    """超时错误"""
    pass


# ==================== 配置异常 ====================

class ConfigurationError(BladeError):
    """配置错误"""
    pass


class MissingAPIKeyError(ConfigurationError):
    """缺少 API 密钥"""
    pass


# ==================== 辅助函数 ====================

def safe_execute(func, default_value=None, error_class=BladeError, log_error=True):
    """
    安全执行函数的装饰器工厂

    Args:
        func: 要执行的函数
        default_value: 异常时返回的默认值
        error_class: 要捕获的异常类
        log_error: 是否记录错误日志

    Returns:
        函数执行结果或默认值
    """
    from functools import wraps
    from loguru import logger

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except error_class as e:
                if log_error:
                    logger.error(f"{func.__name__} failed: {e}")
                return default_value
            except Exception as e:
                if log_error:
                    logger.error(f"{func.__name__} unexpected error: {e}")
                return default_value
        return wrapper
    return decorator


def handle_analysis_error(phase: str, error: Exception, binary_name: str = None):
    """
    统一处理分析阶段的错误

    Args:
        phase: 阶段名称 (phase1, phase2, phase3, phase4)
        error: 异常对象
        binary_name: 二进制文件名（可选）

    Returns:
        格式化的错误信息
    """
    from loguru import logger

    error_info = {
        "phase": phase,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "binary_name": binary_name
    }

    # 根据错误类型决定日志级别
    if isinstance(error, BladeError):
        logger.warning(f"[{phase}] {error}")
    else:
        logger.error(f"[{phase}] Unexpected error: {error}")

    return error_info
