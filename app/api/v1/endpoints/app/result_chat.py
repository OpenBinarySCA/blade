"""
Result Chat API - Interactive chat with TPL detection results using AI agent
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from .....services.tpl_detection.result_file_service import ResultFileService
from .....services.tpl_detection.result_chat import SessionService, ChatStreamService
from .....services.tpl_detection.result_analyzer.result_analyzer import ResultAnalyzer
from ...schemas import ChatMessageRequest, ClearHistoryRequest, ClearHistoryResponse

router = APIRouter()


@router.post("/result_chat/message")
async def send_chat_message(request: ChatMessageRequest):
    """
    Send a chat message and get streaming AI response.

    Uses Server-Sent Events (SSE) for streaming response.

    Args:
        request: ChatMessageRequest containing task_id, message, and optional session_id

    Returns:
        StreamingResponse with SSE data

    Raises:
        HTTPException: 400 if validation fails, 404 if file not found, 500 for other errors
    """
    try:
        # Validate inputs
        if not request.task_id or not request.message:
            raise HTTPException(status_code=400, detail="task_id and message are required")

        if not request.result_minio_path:
            raise HTTPException(status_code=400, detail="result_minio_path is required")

        logger.info(f"Processing chat message for task {request.task_id}")

        # Get or create session
        session_id, session_data = SessionService.get_or_create_session(
            request.session_id,
            request.task_id,
            request.result_minio_path
        )

        # Get result file path (prioritize local file)
        result_file_path = ResultFileService.get_result_file_path(
            request.task_id,
            request.result_minio_path
        )

        # Initialize ResultAnalyzer with session_id
        analyzer = ResultAnalyzer(
            result_path=result_file_path,
            session_id=request.task_id  # Use task_id as session_id for agent conversation history
        )

        # Return SSE streaming response
        return StreamingResponse(
            ChatStreamService.event_stream(analyzer, request.message, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable buffering in nginx
            }
        )

    except FileNotFoundError as e:
        logger.error(f"Result file not found for task {request.task_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Result file not found: {str(e)}")
    except Exception as e:
        logger.error(f"Chat failed for task {request.task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/result_chat/clear", response_model=ClearHistoryResponse)
def clear_chat_history(request: ClearHistoryRequest):
    """
    Clear chat history for a session.

    Args:
        request: ClearHistoryRequest containing session_id

    Returns:
        ClearHistoryResponse with success status and message

    Raises:
        HTTPException: 500 if clearing fails
    """
    try:
        logger.info(f"Clearing chat history for session {request.session_id}")
        success = SessionService.clear_session(request.session_id)

        return ClearHistoryResponse(
            success=success,
            message="Chat history cleared" if success else "Session not found"
        )
    except Exception as e:
        logger.error(f"Failed to clear history for session {request.session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")
