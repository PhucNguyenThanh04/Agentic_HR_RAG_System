from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends
from redis.asyncio import Redis

from src.api.v1.features.employee_onboarding import schemas
from src.api.v1.features.face_profiles import schemas as face_profile_schemas
from src.api.v1.features.face_profiles.service import FaceProfileService, get_face_profile_service
from src.api.v1.features.staff.employees import schemas as employee_schemas
from src.api.v1.features.staff.employees.service import EmployeeService, get_employee_service
from src.api.v1.features.users.service import get_user_service, UserService
from src.core.clients.face_server.clients import FaceServerClient
from src.core.clients.face_server.schemas import AICommitRequest, AIPayloadCreateRequest
from src.core.configs.settings import settings
from src.core.dependencies.dep import get_ai_http_client, get_redis_client
from src.core.security.authentication import hash_password
from src.api.v1.shared.enums import FaceProfileStatus, RoleName, UserStatus
from src.utils.exeptions import (
    BadRequestException,
    ConflictException,
    MLProcessingException,
    NotFoundException,
)
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class EmployeeOnboardingService:
    def __init__(
        self,
        employee_service: EmployeeService,
        face_profile_service: FaceProfileService,
        user_service: UserService,
        face_server_client: FaceServerClient,
        redis_client: Redis,
    ):
        self.employee_service = employee_service
        self.face_profile_service = face_profile_service
        self.user_service = user_service
        self.face_server_client = face_server_client
        self.redis_client = redis_client

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"onboarding:session:{session_id}"

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _default_qdrant_collection() -> str:
        return "face_embeddings"

    async def validate_onboarding_payload(
        self,
        payload: schemas.EmployeeOnboardingStartSessionRequest,
    ) -> None:
        if await self.user_service.email_exists(payload.email):
            raise ConflictException("Email already exists")

        await self.employee_service.department_exists_active(department_id=payload.department_id)
        await self.employee_service.position_exists_active(position_id=payload.position_id)


    async def _save_session_state(self, state: schemas.EmployeeOnboardingSessionState) -> None:
        ttl_seconds = int((state.expires_at - self._utc_now()).total_seconds())
        if ttl_seconds <= 0:
            await self.redis_client.delete(self._session_key(state.session_id))
            raise BadRequestException("Onboarding session expired")

        await self.redis_client.set(
            self._session_key(state.session_id),
            state.model_dump_json(),
            ex=ttl_seconds,
        )

    async def _load_session_state(self, session_id: str) -> schemas.EmployeeOnboardingSessionState:
        raw = await self.redis_client.get(self._session_key(session_id))
        if not raw:
            raise NotFoundException("Onboarding session")

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        state = schemas.EmployeeOnboardingSessionState.model_validate_json(raw)
        if state.expires_at <= self._utc_now():
            await self.redis_client.delete(self._session_key(session_id))
            raise BadRequestException("Onboarding session expired")
        return state

    async def start_onboarding_session(
        self,
        payload: schemas.EmployeeOnboardingStartSessionRequest,
        created_by: uuid.UUID,
    ) -> schemas.EmployeeOnboardingStartSessionResponse:
        await self.validate_onboarding_payload(payload=payload)

        now = self._utc_now()
        ttl_seconds = settings.session_ttl_seconds
        expires_at = now + timedelta(seconds=ttl_seconds)
        session_id = str(uuid.uuid4())

        state = schemas.EmployeeOnboardingSessionState(
            session_id=session_id,
            status=schemas.OnboardingSessionStatus.pending,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            department_id=payload.department_id,
            position_id=payload.position_id,
            valid_photo_count=0,
            min_required_photos=3,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        await self._save_session_state(state)
        logger.info(
            "Onboarding session started: session_id=%s created_by=%s",
            session_id,
            created_by,
        )

        return schemas.EmployeeOnboardingStartSessionResponse(
            session_id=session_id,
            status=state.status,
            expires_at=expires_at,
            min_required_photos=state.min_required_photos,
            current_valid_photos=state.valid_photo_count,
        )

    async def upload_photo_to_session(
        self,
        *,
        session_id: str,
        image_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> schemas.EmployeeOnboardingPhotoUploadResponse:
        state = await self._load_session_state(session_id)

        if state.status in {
            schemas.OnboardingSessionStatus.cancelled,
            schemas.OnboardingSessionStatus.committed,
            schemas.OnboardingSessionStatus.failed,
            schemas.OnboardingSessionStatus.expired,
        }:
            raise BadRequestException(f"Session is not accepting images: {state.status.value}")

        try:
            ai_result = await self.face_server_client.add_photo(
                session_id=session_id,
                image_bytes=image_bytes,
                filename=filename,
                content_type=content_type,
            )
        except httpx.HTTPError as exc:
            logger.exception("AI add_photo failed: session_id=%s", session_id)
            raise MLProcessingException(step="add_photo", reason=str(exc)) from exc

        if ai_result.accepted:
            if ai_result.count is not None:
                state.valid_photo_count = ai_result.count
            else:
                state.valid_photo_count += 1
            state.last_error = None
        else:
            state.last_error = ai_result.reason

        ready = state.valid_photo_count >= state.min_required_photos
        state.status = (
            schemas.OnboardingSessionStatus.ready_to_commit
            if ready
            else schemas.OnboardingSessionStatus.pending
        )
        state.updated_at = self._utc_now()
        await self._save_session_state(state)

        return schemas.EmployeeOnboardingPhotoUploadResponse(
            session_id=session_id,
            accepted=ai_result.accepted,
            reason=ai_result.reason,
            quality_score=ai_result.quality_score,
            valid_photo_count=state.valid_photo_count,
            min_required_photos=state.min_required_photos,
            ready_to_commit=ready,
        )

    async def _mark_session_failed(self, state: schemas.EmployeeOnboardingSessionState, reason: str) -> None:
        state.status = schemas.OnboardingSessionStatus.failed
        state.last_error = reason
        state.updated_at = self._utc_now()
        await self._save_session_state(state)

    async def _rollback_created_entities(
        self,
        *,
        created_face_profile_id: uuid.UUID | None,
        created_employee_id: uuid.UUID | None,
        created_user_id: uuid.UUID | None,
    ) -> None:
        if created_face_profile_id is not None:
            try:
                await self.face_profile_service.delete_face_profile(created_face_profile_id)
            except Exception:
                logger.exception(
                    "Rollback warning: failed to delete face profile %s",
                    created_face_profile_id,
                )
        if created_employee_id is not None:
            try:
                await self.employee_service.hard_delete_employee_for_rollback(created_employee_id)
            except Exception:
                logger.exception(
                    "Rollback warning: failed to delete employee %s",
                    created_employee_id,
                )
        if created_user_id is not None:
            try:
                await self.user_service.delete_user(created_user_id)
            except Exception:
                logger.exception(
                    "Rollback warning: failed to delete user %s",
                    created_user_id,
                )

    async def _rollback_ai_vectors(self, staff_id: str | None) -> None:
        if not staff_id:
            return
        try:
            await self.face_server_client.delete_person(staff_id)
            logger.warning("Rollback cleanup: deleted AI vectors for staff_id=%s", staff_id)
        except Exception:
            logger.exception(
                "Rollback warning: failed to delete AI vectors for staff_id=%s",
                staff_id,
            )

    async def commit_onboarding_session(
        self,
        session_id: str,
    ) -> schemas.EmployeeOnboardingCommitResponse:
        state = await self._load_session_state(session_id)
        if state.status == schemas.OnboardingSessionStatus.committed:
            raise BadRequestException("Session already committed")
        if state.status not in {
            schemas.OnboardingSessionStatus.ready_to_commit,
            schemas.OnboardingSessionStatus.pending,
        }:
            raise BadRequestException(f"Session cannot be committed: {state.status.value}")
        if state.valid_photo_count < state.min_required_photos:
            raise BadRequestException("Not enough valid photos to commit onboarding")

        if await self.user_service.email_exists(state.email):
            raise ConflictException("Email already exists")

        created_user_id: uuid.UUID | None = None
        created_employee_id: uuid.UUID | None = None
        created_face_profile_id: uuid.UUID | None = None
        ai_committed_staff_id: str | None = None

        now_iso = self._utc_now().isoformat()
        try:
            user = await self.user_service.create_user(
                email=state.email,
                password_hash=state.password_hash,
                role_name=RoleName.employee,
                status=UserStatus.active,
            )
            created_user_id = user.user_id

            employee = await self.employee_service.create_employee(
                payload=employee_schemas.EmployeeCreate(
                    user_id=user.user_id,
                    full_name=state.full_name,
                    department_id=state.department_id,
                    position_id=state.position_id,
                ),
                registered_by=state.created_by,
            )
            created_employee_id = employee.employee_id
            if employee.user_id != user.user_id:
                logger.warning(
                    "Onboarding employee missing user link, repairing: employee_id=%s user_id=%s",
                    employee.employee_id,
                    user.user_id,
                )
                employee = await self.employee_service.update_employee(
                    employee.employee_id,
                    employee_schemas.EmployeeUpdate(user_id=user.user_id),
                )
                if employee.user_id != user.user_id:
                    raise RuntimeError("Failed to link onboarding employee to created user")

            profile = await self.face_profile_service.create_face_profile(
                face_profile_schemas.FaceProfileCreate(
                    employee_id=employee.employee_id,
                    qdrant_collection=self._default_qdrant_collection(),
                    registered_by=state.created_by,
                )
            )
            created_face_profile_id = profile.profile_id

            ai_payload = AIPayloadCreateRequest(
                staff_id=str(employee.employee_id),
                face_profile_id=str(profile.profile_id),
                employee_code=employee.employee_code,
                is_active=True,
                created_at=now_iso,
                updated_at=now_iso,
            )
            ai_result = await self.face_server_client.commit(
                AICommitRequest(
                    session_id=session_id,
                    payload=ai_payload,
                )
            )
            ai_committed_staff_id = ai_payload.staff_id

            await self.face_profile_service.update_face_profile(
                profile.profile_id,
                face_profile_schemas.FaceProfileUpdate(
                    status=FaceProfileStatus.active,
                    embedding_version=ai_payload.embedding_version,
                ),
            )

            state.status = schemas.OnboardingSessionStatus.committed
            state.employee_code = employee.employee_code
            state.last_error = None
            state.updated_at = self._utc_now()
            await self.redis_client.delete(self._session_key(session_id))
            logger.info("Onboarding session cleaned after commit: session_id=%s", session_id)

            return schemas.EmployeeOnboardingCommitResponse(
                session_id=session_id,
                status=state.status,
                user_id=user.user_id,
                employee_id=employee.employee_id,
                employee_code=employee.employee_code,
                face_profile_id=profile.profile_id,
                vectors_stored=ai_result.vectors_stored,
            )
        except httpx.HTTPError as exc:
            if created_employee_id is not None:
                await self._rollback_ai_vectors(str(created_employee_id))
            await self._rollback_created_entities(
                created_face_profile_id=created_face_profile_id,
                created_employee_id=created_employee_id,
                created_user_id=created_user_id,
            )
            await self._mark_session_failed(state, f"AI commit failed: {exc}")
            logger.exception("AI commit failed for onboarding session_id=%s", session_id)
            raise MLProcessingException(step="commit", reason=str(exc), task_id=session_id) from exc
        except Exception as exc:
            await self._rollback_ai_vectors(ai_committed_staff_id)
            await self._rollback_created_entities(
                created_face_profile_id=created_face_profile_id,
                created_employee_id=created_employee_id,
                created_user_id=created_user_id,
            )
            await self._mark_session_failed(state, str(exc))
            raise

    async def cancel_onboarding_session(
        self,
        session_id: str,
        cancelled_by: uuid.UUID,
    ) -> schemas.EmployeeOnboardingCancelResponse:
        state = await self._load_session_state(session_id)

        if state.status == schemas.OnboardingSessionStatus.committed:
            raise BadRequestException("Committed session cannot be cancelled")

        try:
            await self.face_server_client.cancel_enrollment(session_id)
        except httpx.HTTPError as exc:
            logger.exception("AI cancel enrollment failed: session_id=%s", session_id)
            raise MLProcessingException(step="cancel", reason=str(exc), task_id=session_id) from exc

        await self.redis_client.delete(self._session_key(session_id))
        logger.info(
            "Onboarding session cancelled: session_id=%s cancelled_by=%s",
            session_id,
            cancelled_by,
        )

        return schemas.EmployeeOnboardingCancelResponse(
            session_id=session_id,
            cancelled=True,
            status=schemas.OnboardingSessionStatus.cancelled,
        )


def get_employee_onboarding_service(
    employee_service: EmployeeService = Depends(get_employee_service),
    face_profile_service: FaceProfileService = Depends(get_face_profile_service),
    user_service: UserService = Depends(get_user_service),
    ai_http_client: httpx.AsyncClient = Depends(get_ai_http_client),
    redis_client: Redis = Depends(get_redis_client),
) -> EmployeeOnboardingService:
    return EmployeeOnboardingService(
        employee_service=employee_service,
        face_profile_service=face_profile_service,
        user_service=user_service,
        face_server_client=FaceServerClient(ai_http_client),
        redis_client=redis_client,
    )
