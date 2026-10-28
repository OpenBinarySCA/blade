"""
Result Analyzer - Interactive agent for analyzing TPL detection results

This module provides an interactive agent that helps users understand and explore
TPL detection results (both single and batch) through natural language queries.
"""

import json
from typing import Optional
from pathlib import Path

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb

from app.services.tpl_detection.models import create_model
from .result_analyzer_prompt import ResultAnalyzerPrompt
from .tools.result_query_tools import ResultQueryTools


class ResultAnalyzer:
    """
    Interactive agent for analyzing TPL detection results.

    This agent provides a conversational interface to explore detection results,
    answer questions about detected libraries, explain reasoning, and provide
    insights into the analysis process.

    Supports both single binary results and batch results automatically.

    Example:
        # Load batch result from file
        analyzer = ResultAnalyzer(result_path="TPL_detection_result.json")
        response = analyzer.agent.run("What libraries were detected?")

        # With streaming
        stream = analyzer.agent.run("Tell me about OpenSSL", stream=True)
        for chunk in stream:
            print(chunk.content, end="")
    """

    def __init__(self,
                 result_path: str,
                 enable_web_search: bool = False,
                 session_id: Optional[str] = None):
        """
        Initialize the Result Analyzer agent.

        Args:
            result_path: Path to a detection result JSON file (batch or single)
            enable_web_search: Whether to enable web search tools (default: False)
            session_id: Session ID for conversation history (default: None, will generate one)

        Raises:
            FileNotFoundError: If result_path doesn't exist
            ValueError: If the file cannot be parsed as JSON
        """
        result_path = Path(result_path)
        if not result_path.exists():
            raise FileNotFoundError(f"Result file not found: {result_path}")

        # Load result as pure dict (not Python objects)
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON file: {e}")

        self.result_source = str(result_path)

        # Detect result type
        if isinstance(self.data, dict):
            if 'detection_results' in self.data:
                # Batch result
                self.result_type = "batch"
                self.binary_count = len(self.data.get('detection_results', []))
            elif 'binary_name' in self.data:
                # Single binary result - wrap it in batch format for consistency
                self.result_type = "single"
                self.binary_count = 1
                # Wrap single result in batch format
                self.data = {
                    "input_file": {
                        "file_name": self.data.get('binary_name', 'unknown'),
                        "file_size": "0 B",
                        "file_type": "application/octet-stream",
                        "readable_type": "Binary file",
                        "file_md5": self.data.get('binary_sha256', '')[:32]  # Use first 32 chars of sha256
                    },
                    "extraction": {
                        "extracted_file_num": 1,
                        "extracted_file_paths": [self.data.get('binary_path', '')]
                    },
                    "detection_results": [self.data]
                }
            else:
                raise ValueError("Unknown result format: missing 'detection_results' or 'binary_name'")
        else:
            raise ValueError(f"Invalid result format: expected dict, got {type(self.data)}")

        # Initialize tools with the loaded data
        self.query_tools = ResultQueryTools(self.data)

        # Build tools list
        tools = [self.query_tools]

        # Optionally add web search
        if enable_web_search:
            from agno.tools.duckduckgo import DuckDuckGoTools
            tools.append(DuckDuckGoTools())

        # Initialize agent with session_id for conversation history
        self.agent = Agent(
            session_id=session_id,  # Use session_id for persistent history
            model=create_model(),
            tools=tools,
            tool_call_limit=10,  # Allow multiple tool calls for complex queries
            instructions=ResultAnalyzerPrompt.SystemPrompt,
            db=InMemoryDb(),
            add_history_to_context=True,  # Enable conversation context
            num_history_messages=5,
            markdown=True  # Enable markdown formatting in responses
        )

    def clear_history(self):
        """Clear the conversation history."""
        if self.agent.db:
            # Clear session from database
            self.agent.db.clear()
