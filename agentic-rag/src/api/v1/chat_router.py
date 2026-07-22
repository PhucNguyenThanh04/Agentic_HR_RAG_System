import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.core.dependenci import get_user_access_token, verify_api_key
from src.features.chat.schemas import ChatRequest, ChatResponse
from src.features.chat.service import ChatService, get_chat_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["Chat"], dependencies=[Depends(verify_api_key)])


@router.post("/message", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    access_token: str = Depends(get_user_access_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        return await chat_service.chat(request, access_token=access_token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail="User authorization failed",
            ) from exc
        raise
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="User context mismatch") from exc
    except Exception as exc:
        logger.exception(
            "Unhandled error in chat endpoint: conversation_id=%s employee_id=%s",
            request.conversation_id,
            request.employee_id,
        )
        raise HTTPException(status_code=500, detail="Agent request failed") from exc


@router.post("/message/stream")
async def chat_stream(
    request: ChatRequest,
    access_token: str = Depends(get_user_access_token),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    try:
        stream = await chat_service.chat_stream(request, access_token=access_token)
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail="User authorization failed",
            ) from exc
        raise
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="User context mismatch") from exc
    except Exception as exc:
        logger.exception(
            "Unhandled error in chat stream endpoint: conversation_id=%s employee_id=%s",
            request.conversation_id,
            request.employee_id,
        )
        raise HTTPException(status_code=500, detail="Agent request failed") from exc
