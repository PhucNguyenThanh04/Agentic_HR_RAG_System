from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.features.documents.schemas import (
    DocumentIngestResponse,
    DocumentVectorDeleteResponse,
)
from src.features.documents.service import DocumentService, get_document_service
from src.core.dependenci import verify_api_key

router = APIRouter(prefix="/api/v1", tags=["Documents"], dependencies=[Depends(verify_api_key)])


@router.post("/rag/documents", response_model=DocumentIngestResponse)
async def upload_document(
    document_id: str = Form(...),
    filename: str = Form(...),
    file_path: str = Form(...),
    allowed_roles: list[str] = Form(...),
    file: UploadFile = File(...),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentIngestResponse:

    try:
        result = await document_service.ingestion(
            file=file,
            document_id=document_id,
            filename=filename,
            file_path=file_path,
            allowed_roles=allowed_roles,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete(
    "/rag/documents/{document_id}/vectors",
    response_model=DocumentVectorDeleteResponse,
)
async def delete_document_vectors(
    document_id: str,
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentVectorDeleteResponse:
    try:
        return await document_service.delete_document_vectors(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
