"""
Chat Stream Service

Handles Server-Sent Events (SSE) streaming for chat responses.
"""
import json
from typing import AsyncGenerator
from loguru import logger

from agno.run.agent import RunEvent
from ..result_analyzer import ResultAnalyzer


class ChatStreamService:
    """Service for handling SSE streaming of chat responses"""

    @staticmethod
    async def event_stream(
        analyzer: ResultAnalyzer,
        message: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Async generator for SSE streaming response.

        Yields Server-Sent Events formatted data including:
        - session_id: Sent first
        - content: AI response chunks
        - tool_call: Tool invocation notifications
        - done: Completion signal
        - error: Error messages

        Args:
            analyzer: ResultAnalyzer instance
            message: User message to process
            session_id: Session ID for the chat

        Yields:
            SSE formatted strings
        """
        try:
            # Send session_id first
            yield ChatStreamService._format_sse({
                'type': 'session_id',
                'session_id': session_id
            })

            # Run agent with streaming
            logger.debug(f"Starting agent stream for session {session_id}")
            stream = analyzer.agent.run(message, stream=True, stream_events=True)

            for chunk in stream:
                if chunk.event == RunEvent.run_content:
                    # Content chunk
                    yield ChatStreamService._format_sse({
                        'type': 'content',
                        'content': chunk.content
                    })

                elif chunk.event == RunEvent.tool_call_started:
                    # Tool call started
                    tool_name = chunk.tool.tool_name if hasattr(chunk.tool, 'tool_name') else 'unknown'
                    yield ChatStreamService._format_sse({
                        'type': 'tool_call',
                        'tool_name': tool_name
                    })
                    logger.debug(f"Tool called: {tool_name}")

            # Send completion signal
            yield ChatStreamService._format_sse({'type': 'done'})
            logger.debug(f"Stream completed for session {session_id}")

        except Exception as e:
            # Send error
            logger.error(f"Stream error for session {session_id}: {e}")
            yield ChatStreamService._format_sse({
                'type': 'error',
                'message': str(e)
            })

    @staticmethod
    def _format_sse(data: dict) -> str:
        """
        Format data as Server-Sent Event.

        Args:
            data: Dictionary to send

        Returns:
            SSE formatted string
        """
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
