# Models Module
# 共享的数据模型和 LLM 工厂

from .response_models import (
    SoftwareContext,
    BinaryInformation,
    LibraryInformation,
    VersionCandidate,
    LLMVersionAnalysisResult
)
from .model_factory import create_model

__all__ = [
    'SoftwareContext',
    'BinaryInformation',
    'LibraryInformation',
    'VersionCandidate',
    'LLMVersionAnalysisResult',
    'create_model'
]
