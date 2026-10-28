"""
BLADE TPL Detection Service

注意：为避免循环导入，DetectionWorkflow 需要显式导入：
    from app.services.tpl_detection.workflow import DetectionWorkflow
"""

from .exceptions import (
    BladeError,
    BinaryParseError,
    FileAccessError,
    LLMAnalysisError,
    Phase2AnalysisError,
    Phase3AnalysisError,
    VersionAnalysisError,
    WorkflowError,
    ConfigurationError,
    MissingAPIKeyError
)
from .config import TPLDetectionConfig, get_config


def __getattr__(name):
    """延迟导入 DetectionWorkflow 以避免循环导入"""
    if name == "DetectionWorkflow":
        from .workflow import DetectionWorkflow
        return DetectionWorkflow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DetectionWorkflow",
    "BladeError",
    "BinaryParseError",
    "FileAccessError",
    "LLMAnalysisError",
    "Phase2AnalysisError",
    "Phase3AnalysisError",
    "VersionAnalysisError",
    "WorkflowError",
    "ConfigurationError",
    "MissingAPIKeyError",
    "TPLDetectionConfig",
    "get_config",
]
