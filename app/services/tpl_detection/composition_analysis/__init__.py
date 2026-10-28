"""
Composition Analysis - 二进制成分分析

一次性 LLM 分析：主程序 + 动态库 + 静态库
"""

from .material_collector import MaterialCollector, AnalysisMaterial
from .composition_analyzer import CompositionAnalyzer
from .response_models import TPLAnalysisResult, LibraryResult

__all__ = [
    # Phase 1: 信息准备
    'MaterialCollector',
    'AnalysisMaterial',
    # Phase 2: LLM 分析
    'CompositionAnalyzer',
    # Response Models
    'TPLAnalysisResult',
    'LibraryResult',
]
