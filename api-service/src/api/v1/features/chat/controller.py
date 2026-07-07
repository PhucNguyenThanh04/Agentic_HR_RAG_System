from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Response, status
from fastapi.responses import StreamingResponse

from src.api.v1.features.chat import schemas
from src.api.v1.features.chat.service import (
    ConversationService,
    get_conversation_service,
)
from src.api.v1.features.staff.models import Employee
from src.api.v1.features.users.models import User
from src.core.dependencies.auth import get_current_employee, get_current_user

router = APIRouter(prefix="/chat", tags=["Conversations"])


@router.post(
    "/",
    response_model=schemas.ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: schemas.ConversationCreateRequest | None = Body(default=None),
    current_employee: Employee = Depends(get_current_employee),
    service: ConversationService = Depends(get_conversation_service),
) -> schemas.ConversationRead:
    return await service.create_conversation(
        payload=payload or schemas.ConversationCreateRequest(),
        current_employee=current_employee,
    )


@router.get("/", response_model=list[schemas.ConversationRead])
async def list_conversations(
    current_employee: Employee = Depends(get_current_employee),
    service: ConversationService = Depends(get_conversation_service),
) -> list[schemas.ConversationRead]:
    return await service.list_conversations(
        current_employee=current_employee,
    )


@router.post(
    "/new-message",
    response_model=schemas.NewMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_new_message(
    payload: schemas.SendMessageRequest,
    current_employee: Employee = Depends(get_current_employee),
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> schemas.NewMessageResponse:
    return await service.send_new_message(
        payload=payload,
        current_employee=current_employee,
        current_user=current_user,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_employee: Employee = Depends(get_current_employee),
    service: ConversationService = Depends(get_conversation_service),
) -> Response:
    await service.delete_conversation(
        conversation_id=conversation_id,
        current_employee=current_employee,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/messages", response_model=list[schemas.ChatMessageRead])
async def list_messages(
    conversation_id: uuid.UUID,
    current_employee: Employee = Depends(get_current_employee),
    service: ConversationService = Depends(get_conversation_service),
) -> list[schemas.ChatMessageRead]:
    return await service.list_messages(
        conversation_id=conversation_id,
        current_employee=current_employee,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=schemas.SendMessageResponse,
)
async def send_message(
    conversation_id: uuid.UUID,
    payload: schemas.SendMessageRequest,
    current_employee: Employee = Depends(get_current_employee),
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> schemas.SendMessageResponse:
    return await service.send_message(
        conversation_id=conversation_id,
        payload=payload,
        current_employee=current_employee,
        current_user=current_user,
    )


@router.post("/{conversation_id}/messages/stream")
async def send_message_stream(
    conversation_id: uuid.UUID,
    payload: schemas.SendMessageRequest,
    current_employee: Employee = Depends(get_current_employee),
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> StreamingResponse:
    stream = await service.send_message_stream(
        conversation_id=conversation_id,
        payload=payload,
        current_employee=current_employee,
        current_user=current_user,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
