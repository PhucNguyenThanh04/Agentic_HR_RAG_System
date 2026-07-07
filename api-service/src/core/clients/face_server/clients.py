from __future__ import annotations

import os
from typing import Any

import httpx

from src.core.clients.face_server.schemas import (
    AIActivatePersonResponse,
    AIAddPhotoResponse,
    AICancelEnrollmentResponse,
    AICommitRequest,
    AICommitResponse,
    AIDeactivatePersonResponse,
    AIDeletePersonResponse,
    AIEnrolledStatusResponse,
    AIHealthResponse,
    AIEnrollPhotoParams,
    AIServerPaths,
)
from src.core.configs.settings import settings
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)

class FaceServerClient:

    def __init__(self, http_client: httpx.AsyncClient,) -> None:
        self._http = http_client
        self._api_key = settings.face_service_api_key
        self._default_headers = {"X-API-Key": self._api_key} if self._api_key else {}

    async def health(self) -> AIHealthResponse:
        data = await self._request_json("GET", AIServerPaths.HEALTH, require_api_key=False)
        return AIHealthResponse.model_validate(data)

    async def add_photo(
        self,
        session_id: str,
        image_bytes: bytes,
        filename: str = "face.jpg",
        content_type: str = "image/jpeg",
    ) -> AIAddPhotoResponse:
        params = AIEnrollPhotoParams(session_id=session_id)
        files = {"file": (filename, image_bytes, content_type)}
        data = await self._request_json(
            method="POST",
            path=AIServerPaths.ENROLL_PHOTO,
            params=params.model_dump(mode="json"),
            files=files,
        )
        logger.debug(f"add_photo response: {data}")
        return AIAddPhotoResponse.model_validate(data)

    async def commit(self, body: AICommitRequest) -> AICommitResponse:
        data = await self._request_json(
            method="POST",
            path=AIServerPaths.ENROLL_COMMIT,
            json=body.model_dump(mode="json", exclude_none=True),
        )
        logger.debug(f"commit response: {data}")
        return AICommitResponse.model_validate(data)

    async def re_enroll(self, body: AICommitRequest) -> AICommitResponse:
        data = await self._request_json(
            method="POST",
            path=AIServerPaths.ENROLL_REENROLL,
            json=body.model_dump(mode="json", exclude_none=True),
        )
        logger.debug(f"re_enroll response: {data}")
        return AICommitResponse.model_validate(data)

    async def cancel_enrollment(self, session_id: str) -> AICancelEnrollmentResponse:
        data = await self._request_json(
            method="DELETE",
            path=AIServerPaths.enroll_cancel(session_id),
        )
        logger.debug(f"cancel_enrollment response: {data}")
        return AICancelEnrollmentResponse.model_validate(data)

    async def delete_person(self, staff_id: str) -> AIDeletePersonResponse:
        data = await self._request_json(
            method="DELETE",
            path=AIServerPaths.delete_person(staff_id),
        )
        logger.debug(f"delete_person response: {data}")
        return AIDeletePersonResponse.model_validate(data)

    async def deactivate_person(self, staff_id: str) -> AIDeactivatePersonResponse:
        data = await self._request_json(
            method="PATCH",
            path=AIServerPaths.deactivate_person(staff_id),
        )
        logger.debug(f"deactivate_person response: {data}")
        return AIDeactivatePersonResponse.model_validate(data)

    async def activate_person(self, staff_id: str) -> AIActivatePersonResponse:
        data = await self._request_json(
            method="PATCH",
            path=AIServerPaths.activate_person(staff_id),
        )
        logger.debug(f"activate_person response: {data}")
        return AIActivatePersonResponse.model_validate(data)

    async def check_enrolled_status(self, staff_id: str) -> AIEnrolledStatusResponse:
        data = await self._request_json(
            method="GET",
            path=AIServerPaths.enrolled_status(staff_id),
        )
        logger.debug(f"check_enrolled_status response: {data}")
        return AIEnrolledStatusResponse.model_validate(data)

    async def _request_json(
        self,
        *,
        method: str,
        path: str,
        require_api_key: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        if require_api_key:
            headers.update(self._default_headers)

        response = await self._http.request(method, path, headers=headers, **kwargs)
        response.raise_for_status()
        logger.debug(f"HTTP {method} {path} | status={response.status_code} | response={response.text}")
        return response.json()


def get_face_server_client(http_client: httpx.AsyncClient) -> FaceServerClient:
    return FaceServerClient(http_client)
