from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from src.api.v1.features.documents import schemas
from src.api.v1.features.documents.service import (
    DocumentService,
    get_document_service,
)
from src.api.v1.features.staff.models import Employee
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import get_current_employee, require_roles

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/", response_model=schemas.DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    title: str = Form(...),
    allowed_roles: list[str] = Form(...),
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
    current_employee: Employee = Depends(get_current_employee),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.DocumentRead:
    return await service.upload_document(
        title=title,
        allowed_roles=allowed_roles,
        file=file,
        current_employee=current_employee,
    )


@router.get("/", response_model=dict)
async def list_documents(
    query: schemas.DocumentListQuery = Depends(),
    service: DocumentService = Depends(get_document_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> dict:
    return await service.list_documents(query)


@router.get("/{document_id}", response_model=schemas.DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> schemas.DocumentRead:
    return await service.get_document(document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    service: DocumentService = Depends(get_document_service),
    _: User = Depends(require_roles(RoleName.admin)),
) -> Response:
    await service.delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
