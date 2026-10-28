"""
Agent Analysis Response Models

保留用于其他模块使用的模型：
- SoftwareContext: 软件上下文分析
- BinaryInformation: 二进制信息
- VersionCandidate, LLMVersionAnalysisResult: 版本分析
"""

from dataclasses import dataclass
from typing import Optional, List, Literal

from pydantic import BaseModel, Field


# ==================== Binary Information ====================

class LibraryInformation(BaseModel):
    """
    Agent answer format for library information
    """
    name: str = Field(
        description="The name of the third-party library."
    )
    description: str = Field(
        description="A concise description of the third-party library."
    )

    def customer_serialize(self) -> dict:
        return {
            "name": self.name,
            "description": self.description
        }

    @classmethod
    def init_from_dict(cls, data: dict):
        return cls(
            name=data.get("name", ""),
            description=data.get("description", "")
        )


class BinaryInformation(BaseModel):
    """
    Agent answer format for binary analysis
    """
    name: str = Field(
        description="The name of this binary."
    )
    description: str = Field(
        description="Comprehensive description of the binary, including what it is, its main function, storage use cases, security considerations, and any other useful information about this binary."
    )
    source_library: Optional[LibraryInformation] = Field(
        default=None,
        description="Information about the library or framework that may have compiled or generated this binary (if applicable)."
    )

    def customer_serialize(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "source_library": self.source_library.customer_serialize() if self.source_library else None
        }

    @classmethod
    def init_from_dict(cls, data: dict):
        source_library_data = data.get("source_library", None)
        source_library = LibraryInformation.init_from_dict(source_library_data) if source_library_data else None

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            source_library=source_library
        )


# ==================== Software Context ====================

class SoftwareContext(BaseModel):
    """Software context analysis results"""
    software_type: str = Field(default="unknown",
                               description="Software type: embedded_system, web_application, mobile_app, desktop_application, library, system_utility, database")
    primary_purpose: str = Field(default="", description="Primary function and purpose description")
    technology_stack: List[str] = Field(default_factory=list, description="Detected technology stack and frameworks")
    deployment_environment: str = Field(default="unknown",
                                        description="Inferred deployment environment: embedded, server, desktop, mobile, etc.")
    key_components: List[str] = Field(default_factory=list, description="Identified key components and modules")
    directory_analysis: str = Field(default="", description="Directory structure analysis summary")
    architecture_pattern: str = Field(default="unknown", description="Identified software architecture pattern")
    build_system: str = Field(default="unknown", description="Build system type: make, cmake, autotools, etc.")
    confidence_level: str = Field(default="LOW", description="Analysis confidence level: HIGH/MEDIUM/LOW")

    def customer_serialize(self) -> dict:
        return {
            "software_type": self.software_type,
            "primary_purpose": self.primary_purpose,
            "technology_stack": self.technology_stack,
            "deployment_environment": self.deployment_environment,
            "key_components": self.key_components,
            "directory_analysis": self.directory_analysis,
            "architecture_pattern": self.architecture_pattern,
            "build_system": self.build_system,
            "confidence_level": self.confidence_level
        }


# ==================== Version Analysis ====================

ConfidenceLevel = Literal["high", "medium", "low", "unknown"]


@dataclass
class VersionCandidate(BaseModel):
    version: str = Field(
        ...,
        description="One possible version of the target library, or 'unknown' if indeterminate."
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level for this candidate: 'high', 'medium', 'low', or 'unknown'."
    )
    evidences: List[str] = Field(
        ...,
        description="Exact raw strings from the binary that support this candidate; no alterations or commentary."
    )


@dataclass
class LLMVersionAnalysisResult(BaseModel):
    versions: List[VersionCandidate] = Field(
        ...,
        description="All plausible version candidates for the target library, each with confidence and evidence."
    )
    reasoning: str = Field(
        ...,
        description="Global explanation of evidence prioritization and conflict handling."
    )
