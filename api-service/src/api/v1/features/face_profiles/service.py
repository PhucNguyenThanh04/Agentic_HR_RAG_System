from __future__ import annotations

import uuid

import httpx
from fastapi import Depends

from src.api.v1.features.face_profiles import schemas
from src.api.v1.features.face_profiles.face_profile_repo import (
    FaceProfileRepo,
    get_face_profile_repo,
)
from src.api.v1.shared.enums import FaceProfileStatus
from src.core.clients.face_server.clients import FaceServerClient
from src.core.dependencies.dep import get_ai_http_client
from src.utils.exeptions import BadRequestException, MLProcessingException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class FaceProfileService:
    def __init__(
        self,
        face_profile_repo: FaceProfileRepo,
        face_server_client: FaceServerClient,
    ):
        self.face_profile_repo = face_profile_repo
        self.face_server_client = face_server_client

    @staticmethod
    def _to_read(profile) -> schemas.FaceProfileRead:
        return schemas.FaceProfileRead.model_validate(profile)

    async def create_face_profile(self, payload: schemas.FaceProfileCreate) -> schemas.FaceProfileRead:
        if not await self.face_profile_repo.employee_exists(payload.employee_id):
            raise BadRequestException("Employee not found")
        if payload.registered_by is not None and not await self.face_profile_repo.user_exists(
            payload.registered_by
        ):
            raise BadRequestException("Registrar user not found")

        profile = await self.face_profile_repo.create_face_profile(payload)
        logger.info("Face profile created: profile_id=%s", profile.profile_id)
        return self._to_read(profile)

    async def get_face_profile(self, profile_id: uuid.UUID) -> schemas.FaceProfileRead:
        profile = await self.face_profile_repo.get_profile_by_id(profile_id)
        if profile is None:
            logger.warning("Face profile not found: profile_id=%s", profile_id)
            raise NotFoundException("Face profile")
        return self._to_read(profile)

    async def get_face_profile_by_employee(self, employee_id: uuid.UUID) -> schemas.FaceProfileRead:
        profile = await self.face_profile_repo.get_profile_by_employee_id(employee_id)
        if profile is None:
            logger.warning("Face profile not found by employee: employee_id=%s", employee_id)
            raise NotFoundException("Face profile")
        return self._to_read(profile)

    async def list_face_profiles(self, query: schemas.FaceProfileListQuery) -> dict:
        profiles, total = await self.face_profile_repo.list_face_profiles(
            page=query.page,
            page_size=query.page_size,
            employee_id=query.employee_id,
            status=query.status,
        )
        return {
            "items": [self._to_read(profile) for profile in profiles],
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }

    async def update_face_profile(
        self,
        profile_id: uuid.UUID,
        payload: schemas.FaceProfileUpdate,
    ) -> schemas.FaceProfileRead:
        existing = await self.face_profile_repo.get_profile_by_id(profile_id)
        if existing is None:
            raise NotFoundException("Face profile")

        if payload.registered_by is not None and not await self.face_profile_repo.user_exists(
            payload.registered_by
        ):
            raise BadRequestException("Registrar user not found")

        if (
            payload.status == FaceProfileStatus.revoked
            and existing.status != FaceProfileStatus.revoked
        ):
            await self._deactivate_ai_vectors_for_profile(existing, reason="face_profile_update_revoked")

        updated = await self.face_profile_repo.update_face_profile(profile_id, payload)
        logger.info("Face profile updated: profile_id=%s", profile_id)
        return self._to_read(updated)

    async def _deactivate_ai_vectors_for_profile(self, profile, *, reason: str) -> None:
        try:
            result = await self.face_server_client.deactivate_person(str(profile.employee_id))
            logger.info(
                "AI vectors deactivated for face profile: profile_id=%s employee_id=%s vectors_updated=%s reason=%s",
                profile.profile_id,
                profile.employee_id,
                result.vectors_updated,
                reason,
            )
        except httpx.HTTPError as exc:
            logger.exception(
                "Failed to deactivate AI vectors for face profile: profile_id=%s employee_id=%s reason=%s",
                profile.profile_id,
                profile.employee_id,
                reason,
            )
            raise MLProcessingException(
                step="deactivate_face_profile_vectors",
                reason=str(exc),
                task_id=str(profile.profile_id),
            ) from exc

    async def revoke_face_profile(
        self,
        profile_id: uuid.UUID,
        payload: schemas.RevokeFaceProfileRequest,
    ) -> schemas.FaceProfileRead:
        existing = await self.face_profile_repo.get_profile_by_id(profile_id)
        if existing is None:
            raise NotFoundException("Face profile")

        if existing.status != FaceProfileStatus.revoked:
            await self._deactivate_ai_vectors_for_profile(existing, reason="face_profile_revoke")

        revoked = await self.face_profile_repo.revoke_face_profile(profile_id, payload.reason)
        logger.info("Face profile revoked: profile_id=%s", profile_id)
        return self._to_read(revoked)

    async def delete_face_profile(self, profile_id: uuid.UUID) -> None:
        existing = await self.face_profile_repo.get_profile_by_id(profile_id)
        if existing is None:
            raise NotFoundException("Face profile")
        await self._deactivate_ai_vectors_for_profile(existing, reason="face_profile_delete")
        await self.face_profile_repo.delete_face_profile(profile_id)
        logger.info(
            "Face profile deleted with AI vector deactivation: profile_id=%s employee_id=%s",
            profile_id,
            existing.employee_id,
        )


def get_face_profile_service(
    face_profile_repo: FaceProfileRepo = Depends(get_face_profile_repo),
    ai_http_client: httpx.AsyncClient = Depends(get_ai_http_client),
) -> FaceProfileService:
    return FaceProfileService(
        face_profile_repo=face_profile_repo,
        face_server_client=FaceServerClient(ai_http_client),
    )
