"""
Model Factory for LLM providers
支持多种LLM提供商：OpenAI, Anthropic, Ollama, OpenRouter
"""

from typing import Optional
from loguru import logger

from app.config import settings
from ..exceptions import ModelCreationError, MissingAPIKeyError


def create_model(provider: Optional[str] = None, model_id: Optional[str] = None):
    """
    根据配置创建对应的LLM模型
    
    Args:
        provider: LLM提供商 ("openai", "anthropic", "ollama")
        model_id: 模型ID
        
    Returns:
        LLM模型实例
        
    Raises:
        ValueError: 当提供商不支持或配置错误时
    """
    # 使用配置中的默认值
    provider = provider or settings.LLM_PROVIDER
    model_id = model_id or settings.LLM_MODEL_ID
    
    logger.debug(f"Creating model: provider={provider}, model_id={model_id}")
    
    try:
        if provider.lower() == "openai":
            return _create_openai_model(model_id)
        elif provider.lower() == "anthropic":
            return _create_anthropic_model(model_id)
        elif provider.lower() == "ollama":
            return _create_ollama_model(model_id)
        elif provider.lower() == "openrouter":
            return _create_openrouter_model(model_id)
        else:
            raise ModelCreationError(f"Unsupported LLM provider: {provider}", {"provider": provider})
    except (ModelCreationError, MissingAPIKeyError):
        raise
    except Exception as e:
        logger.error(f"Failed to create model: {e}")
        raise ModelCreationError(f"Failed to create model: {e}", {"provider": provider, "model_id": model_id})


def _create_openai_model(model_id: str):
    """创建OpenAI模型"""
    from agno.models.openai import OpenAIChat

    if not settings.OPENAI_API_KEY:
        raise MissingAPIKeyError("OPENAI_API_KEY is required for OpenAI models", {"provider": "openai"})

    return OpenAIChat(
        id=model_id,
        api_key=settings.OPENAI_API_KEY,
        temperature=1,  # 添加temperature参数，设为0获得最大确定性
        seed=42,        # 添加seed参数，确保可重现性
    )


def _create_anthropic_model(model_id: str):
    """创建Anthropic模型"""
    from agno.models.anthropic import Claude

    if not settings.ANTHROPIC_API_KEY:
        raise MissingAPIKeyError("ANTHROPIC_API_KEY is required for Anthropic models", {"provider": "anthropic"})

    return Claude(
        id=model_id,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=1,  # 添加temperature参数，虽然不能完全确定性，但能减少随机性
        # 注意：Anthropic不支持seed参数
    )


def _create_ollama_model(model_id: str):
    """创建Ollama模型"""
    from agno.models.ollama import Ollama

    kwargs = {
        "id": model_id,
    }

    if settings.OLLAMA_BASE_URL:
        kwargs["host"] = settings.OLLAMA_BASE_URL

    return Ollama(**kwargs)


def _create_openrouter_model(model_id: str):
    """创建OpenRouter模型"""
    from agno.models.openrouter import OpenRouter

    if not settings.OPENROUTER_API_KEY:
        raise MissingAPIKeyError("OPENROUTER_API_KEY is required for OpenRouter models", {"provider": "openrouter"})

    return OpenRouter(
        id=model_id,
        api_key=settings.OPENROUTER_API_KEY,
        max_tokens=100000,  # 默认1024太小，增加到100K
        max_retries=3,      # 失败时重试3次
        temperature=1,
        seed=42,
    )


def get_supported_providers():
    """获取支持的LLM提供商列表"""
    return ["openai", "anthropic", "ollama", "openrouter"]


def get_default_model_config():
    """获取默认模型配置"""
    return {
        "provider": settings.LLM_PROVIDER,
        "model_id": settings.LLM_MODEL_ID
    }