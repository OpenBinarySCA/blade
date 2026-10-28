import os
import traceback
from pathlib import Path

from agno.run.agent import RunOutput
from loguru import logger

from agno.agent import Agent
from agno.tools.file import FileTools
from agno.tools.duckduckgo import DuckDuckGoTools
from ..models import create_model, SoftwareContext


class ContextAnalyzer:
    """
    Smart Context Analyzer - Intelligently analyzes software projects with minimal operations
    """

    def __init__(self, enable_web_search: bool = True):
        self.enable_web_search = enable_web_search


        # Smart analysis instructions
        self.instructions = [
            "You are an expert software architect with pattern recognition skills for rapid project analysis.",
            "",
            "MISSION: Intelligently determine software type and context using MINIMAL file operations.",
            "",
            "SMART ANALYSIS STRATEGY:",
            "",
            "STEP 1: ROOT DIRECTORY INTELLIGENCE",
            "- Start with root directory listing ONLY",
            "- Look for OBVIOUS type indicators that allow immediate classification",
            "- IF classification is CLEAR from root directory → STOP and respond immediately",
            "- IF unclear → proceed to Step 2",
            "",
            "IMMEDIATE CLASSIFICATION INDICATORS (Root Directory Only):",
            "",
            "EMBEDDED_SYSTEM (HIGH confidence from root):",
            "- Directories: boot/, kernel/, firmware/, drivers/, u-boot/",
            "- Files: *.dts, *.dtb, linker.ld, defconfig",
            "- Patterns: cross-compilation evidence, board constants",
            "",
            "WEB_APPLICATION (HIGH confidence from root):",
            "- Files: package.json, requirements.txt, composer.json, Gemfile",
            "- Directories: public/, static/, www/, templates/",
            "- Patterns: web framework indicators",
            "",
            "MOBILE_APP (HIGH confidence from root):",
            "- Android: AndroidManifest.xml, build.gradle, res/, src/",
            "- iOS: Info.plist, *.xcodeproj/, *.xcworkspace/",
            "- React Native: package.json + android/ + ios/",
            "",
            "DESKTOP_APPLICATION (HIGH confidence from root):",
            "- Files: *.pro, CMakeLists.txt, configure.ac",
            "- Directories: src/, include/, with GUI indicators",
            "",
            "LIBRARY/SDK (HIGH confidence from root):",
            "- Directories: lib/, include/, src/, examples/",
            "- Files: *.so, *.a, header files structure",
            "",
            "STEP 2: SELECTIVE DEEP DIVE (Only if Step 1 unclear)",
            "- Check 1-2 key subdirectories that might clarify type",
            "- Read critical config files: README, main build files",
            "- Look for additional context clues",
            "",
            "STEP 3: DOCUMENTATION CHECK (Last resort)",
            "- Read README, DESCRIPTION, or similar docs",
            "- Only if previous steps inconclusive",
            "",
            "DECISION RULES:",
            "- CONFIDENCE HIGH: Clear, obvious indicators from root directory",
            "- CONFIDENCE MEDIUM: Requires some file content analysis",
            "- CONFIDENCE LOW: Ambiguous or conflicting evidence",
            "",
            "EFFICIENCY MANDATES:",
            "- MAXIMUM 3-4 file operations total",
            "- STOP immediately when confident",
            "- Prefer pattern recognition over deep analysis",
            "- Focus on ACTIONABLE context for binary analysis",
            "",
            "RESPONSE STRATEGY:",
            "- Be decisive when evidence is clear",
            "- Acknowledge uncertainty when evidence is limited",
            "- Provide useful context even with limited information"
        ]

    def analyze_software_context(self, root_path: str) -> (SoftwareContext, RunOutput):
        """
        Intelligently analyze software project context with minimal operations
        """
        if not os.path.exists(root_path):
            raise ValueError(f"Root path does not exist: {root_path}")

        logger.debug(f"\n=== SMART SOFTWARE CONTEXT ANALYSIS ===")
        logger.debug(f"Analyzing: {root_path}")

        try:
            # Create tools with specific base directory
            tools = [FileTools(
                base_dir=Path(root_path),
                read_files=True,
                list_files=True,
                save_files=False
            )]

            if self.enable_web_search:
                tools.append(DuckDuckGoTools())

            # Create agent for this analysis
            agent = Agent(
                model=create_model(),
                tools=tools,
                instructions=self.instructions,
                response_model=SoftwareContext,
                show_tool_calls=True,
            )

            # Build smart analysis prompt
            prompt = self._build_smart_prompt(root_path)

            # Execute smart analysis
            response = agent.run(prompt)
            context_result = response.content

            logger.debug(
                f"Analysis completed: {context_result.software_type} (confidence: {context_result.confidence_level})")

            return context_result, response

        except Exception as e:
            logger.error(f"Smart analysis failed: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            return SoftwareContext(
                software_type="unknown",
                primary_purpose=f"Analysis failed: {str(e)}",
                confidence_level="LOW"
            ), None

    def _build_smart_prompt(self, root_path: str) -> str:
        """Build intelligent analysis prompt"""
        return f"""SMART SOFTWARE PROJECT ANALYSIS

TARGET: {root_path}

ANALYSIS PROTOCOL:
Use intelligent, layered approach to minimize file operations while maximizing accuracy.

STEP 1 - ROOT DIRECTORY SCAN:
List root directory contents and analyze patterns for immediate classification.

DECISION POINT 1:
- IF obvious type indicators present → classify immediately with HIGH confidence
- IF partially clear → proceed to Step 2 for verification  
- IF unclear → proceed to Step 2 for deeper investigation

STEP 2 - SELECTIVE INVESTIGATION (Only if needed):
Based on Step 1 findings, selectively examine:
- Key subdirectories that might clarify software type
- Critical configuration files
- Build system files

STEP 3 - DOCUMENTATION CHECK (Last resort):
- Read README or primary documentation
- Only if previous steps inconclusive

EFFICIENCY TARGETS:
- Minimize file operations (3-4 maximum)
- Be decisive when evidence is clear
- Provide actionable context for binary composition analysis

EXPECTED BEHAVIOR:
Start with root directory listing. Stop and respond immediately if classification is obvious.
Only investigate further if genuinely uncertain about software type.

Begin analysis now."""