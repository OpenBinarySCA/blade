"""
Explanation Generator - 生成用户友好的分析说明

将技术性的检测结果转换为用户友好的自然语言解释
"""

import time
from typing import List, Optional, Dict, Any, Tuple
from loguru import logger

from agno.agent import Agent

from ....interface import Library
from ..models import create_model
from .prompts import ExplanationPrompt


class ExplanationGenerator:
    """
    分析说明生成器

    将技术性的检测结果转换为用户友好的自然语言解释
    """

    def __init__(self, model_id: Optional[str] = None):
        """
        初始化说明生成器

        Args:
            model_id: 使用的模型ID，默认使用配置中的 LLM_MODEL_ID
        """
        self.model_id = model_id
        self.agent = Agent(
            model=create_model(model_id=model_id),  # None 会使用 settings 中的默认值
            instructions=ExplanationPrompt.SYSTEM_PROMPT
        )

    def generate(self, library: Library) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        为单个库生成用户友好的说明

        Args:
            library: 检测到的库对象

        Returns:
            Tuple[str, Optional[Dict]]: (用户友好的英文说明, LLM成本信息)
        """
        prompt = self._build_prompt(library)

        try:
            # 记录 LLM 调用时间
            llm_start = time.perf_counter()
            response = self.agent.run(prompt)
            llm_duration = time.perf_counter() - llm_start

            # 提取 LLM 成本信息（包含 duration）
            costs = response.metrics.to_dict() if hasattr(response, 'metrics') and response.metrics else {}
            costs["duration"] = llm_duration
            costs["library"] = library.name

            return response.content.strip(), costs
        except Exception as e:
            logger.warning(f"Failed to generate explanation for {library.name}: {e}")
            return "", None

    def generate_batch(self, libraries: List[Library]) -> List[Dict[str, Any]]:
        """
        批量生成说明，直接更新 Library 对象的 user_explanation 字段

        Args:
            libraries: 库对象列表

        Returns:
            List[Dict]: 每次 LLM 调用的成本信息列表
        """
        all_costs = []
        for lib in libraries:
            if lib.name and lib.name != "unknown":  # 跳过 unknown
                explanation, costs = self.generate(lib)
                lib.user_explanation = explanation
                if costs:
                    all_costs.append(costs)
                logger.debug(f"Generated explanation for {lib.name}")
        return all_costs

    def _build_prompt(self, library: Library) -> str:
        """
        构建输入 prompt

        Args:
            library: 库对象

        Returns:
            格式化的 prompt 字符串
        """
        parts = []

        # 基本信息
        parts.append(f"Library: {library.name}")
        if library.component_name:
            parts.append(f"Component: {library.component_name}")
        parts.append(f"Category: {library.binary_category}")
        parts.append(f"Integration Type: {library.library_integration_type}")

        # 证据
        if library.evidences:
            parts.append("\nEvidences found:")
            for ev in library.evidences[:10]:  # 限制数量避免过长
                parts.append(f"- {ev}")

        # 识别推理（内部）
        if library.identify_reasoning:
            parts.append(f"\nInternal reasoning: {library.identify_reasoning[:500]}")  # 截断

        # 版本信息
        if library.versions:
            version_str = library.versions[0].version if library.versions else None
            confidence = library.versions[0].confidence if library.versions else None
            if version_str:
                parts.append(f"\nVersion: {version_str}")
                if confidence:
                    parts.append(f"Version confidence: {confidence}")

        if library.version_reasoning:
            parts.append(f"Version reasoning: {library.version_reasoning[:300]}")  # 截断

        return "\n".join(parts)
