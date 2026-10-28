"""
LLM 响应模型

一次性分析：主程序 + 动态库 + 静态库
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# 简单响应模型（消融实验用）
# =============================================================================

class SimpleLibraryJudgment(BaseModel):
    """简单的库判定结果（消融实验用）"""
    name: str = Field(description="Library name - must exactly match a candidate name from input")
    is_true_positive: bool = Field(description="Whether this library is truly present in the binary")
    reasoning: str = Field(default="", description="Brief reason for the judgment")


class SimpleAnalysisResult(BaseModel):
    """简单分析结果（消融实验用）"""
    results: List[SimpleLibraryJudgment] = Field(default_factory=list)


# =============================================================================
# 完整响应模型
# =============================================================================

class LibraryResult(BaseModel):
    """单个库识别结果"""

    name: str = Field(
        description="Library name - use canonical project name (e.g., 'openssl', 'android_system_core', 'alsa-lib')"
    )

    component_name: Optional[str] = Field(
        default=None,
        description="Specific component if identifiable (e.g., 'libssl', 'liblog'), otherwise null"
    )

    category: str = Field(
        description="Library category: android_platform, third_party_library, linux_kernel, system_library, unknown_program"
    )

    description: str = Field(
        default="",
        description="Brief library description"
    )

    evidences: List[str] = Field(
        default_factory=list,
        description="Evidence items from binary (copyright, version, symbols, strings, paths)"
    )

    reasoning: str = Field(
        default="",
        description="Analysis process: type classification, evidence analysis, conclusion"
    )


class ExcludedCandidate(BaseModel):
    """被排除的候选库"""

    name: str = Field(
        description="Candidate name exactly as provided in input"
    )

    fp_type: str = Field(
        description="False positive type: C1, C2, C3, C4, or C5"
    )

    reasoning: str = Field(
        default="",
        description="Brief explanation of why this candidate was excluded"
    )


class TPLAnalysisResult(BaseModel):
    """TPL 一次性分析结果"""

    main_program: LibraryResult

    dynamic_dependencies: List[LibraryResult] = Field(default_factory=list)

    static_dependencies: List[LibraryResult] = Field(default_factory=list)

    excluded_candidates: List[ExcludedCandidate] = Field(default_factory=list)
