from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.features.face_profiles import schemas
from src.api.v1.features.face_profiles.models import FaceProfile
from src.api.v1.features.staff.models import Employee
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import FaceProfileStatus
from src.core.db.database import get_db
from src.utils.exeptions import ConflictException, DatabaseException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class FaceProfileRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def employee_exists(self, employee_id: uuid.UUID) -> bool:
        stmt = select(Employee.employee_id).where(Employee.employee_id == employee_id)
        return (await self.db.execute(stmt)).first() is not None

    async def user_exists(self, user_id: uuid.UUID | None) -> bool:
        if user_id is None:
            return False
        stmt = select(User.user_id).where(User.user_id == user_id)
        return (await self.db.execute(stmt)).first() is not None

    async def get_profile_by_id(self, profile_id: uuid.UUID) -> FaceProfile | None:
        return await self.db.scalar(select(FaceProfile).where(FaceProfile.profile_id == profile_id))

    async def get_profile_or_404(self, profile_id: uuid.UUID) -> FaceProfile:
        profile = await self.get_profile_by_id(profile_id)
        if profile is None:
            raise NotFoundException("Face profile")
        return profile

    async def get_profile_by_employee_id(self, employee_id: uuid.UUID) -> FaceProfile | None:
        return await self.db.scalar(
            select(FaceProfile).where(FaceProfile.employee_id == employee_id)
        )

    async def list_face_profiles(
        self,
        page: int = 1,
        page_size: int = 20,
        employee_id: uuid.UUID | None = None,
        status: FaceProfileStatus | None = None,
    ) -> tuple[list[FaceProfile], int]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        offset = (page - 1) * page_size

        stmt: Select = select(FaceProfile)
        if employee_id is not None:
            stmt = stmt.where(FaceProfile.employee_id == employee_id)
        if status is not None:
            stmt = stmt.where(FaceProfile.status == status)

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int((await self.db.scalar(count_stmt)) or 0)

        result = await self.db.execute(
            stmt.order_by(FaceProfile.created_at.desc()).offset(offset).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def create_face_profile(self, payload: schemas.FaceProfileCreate) -> FaceProfile:
        existing = await self.get_profile_by_employee_id(payload.employee_id)
        if existing is not None:
            raise ConflictException("Face profile for employee already exists")

        profile = FaceProfile(
            employee_id=payload.employee_id,
            status=FaceProfileStatus.pending,
            qdrant_collection=payload.qdrant_collection.strip(),
            registered_by=payload.registered_by,
        )
        self.db.add(profile)
        try:
            await self.db.commit()
            await self.db.refresh(profile)
            return profile
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create face profile: employee_id=%s",
                payload.employee_id,
            )
            raise DatabaseException("Failed to create face profile") from exc

    async def update_face_profile(
        self,
        profile_id: uuid.UUID,
        payload: schemas.FaceProfileUpdate,
    ) -> FaceProfile:
        profile = await self.get_profile_or_404(profile_id)
        changed = False
        values = payload.model_dump(exclude_unset=True)

        for field in (
            "status",
            "qdrant_collection",
            "embedding_model",
            "embedding_version",
            "registered_by",
            "revocation_reason",
            "revoked_at",
        ):
            if field not in values:
                continue
            value = values[field]
            if isinstance(value, str):
                value = value.strip() or None
            if getattr(profile, field) != value:
                setattr(profile, field, value)
                changed = True

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update face profile: profile_id=%s",
                    profile_id,
                )
                raise DatabaseException("Failed to update face profile") from exc

        updated = await self.get_profile_by_id(profile_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated face profile")
        return updated

    async def revoke_face_profile(self, profile_id: uuid.UUID, reason: str) -> FaceProfile:
        profile = await self.get_profile_or_404(profile_id)
        profile.status = FaceProfileStatus.revoked
        profile.revocation_reason = reason.strip()
        profile.revoked_at = datetime.now(timezone.utc)

        try:
            await self.db.commit()
            await self.db.refresh(profile)
            return profile
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to revoke face profile: profile_id=%s", profile_id)
            raise DatabaseException("Failed to revoke face profile") from exc

    async def delete_face_profile(self, profile_id: uuid.UUID) -> None:
        profile = await self.get_profile_or_404(profile_id)
        try:
            await self.db.delete(profile)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to delete face profile: profile_id=%s", profile_id)
            raise DatabaseException("Failed to delete face profile") from exc

    async def ensure_pending_profile(
        self,
        *,
        employee_id: uuid.UUID,
        qdrant_collection: str,
        registered_by: uuid.UUID | None = None,
    ) -> FaceProfile:
        existing = await self.get_profile_by_employee_id(employee_id)
        if existing is None:
            return await self.create_face_profile(
                schemas.FaceProfileCreate(
                    employee_id=employee_id,
                    qdrant_collection=qdrant_collection,
                    registered_by=registered_by,
                )
            )

        existing.status = FaceProfileStatus.pending
        existing.qdrant_collection = qdrant_collection.strip()
        existing.registered_by = registered_by
        existing.revocation_reason = None
        existing.revoked_at = None
        try:
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to ensure pending face profile: employee_id=%s",
                employee_id,
            )
            raise DatabaseException("Failed to prepare pending face profile") from exc

    async def mark_profile_active(
        self,
        *,
        profile_id: uuid.UUID,
        embedding_model: str | None = None,
        embedding_version: str | None = None,
    ) -> FaceProfile:
        profile = await self.get_profile_or_404(profile_id)
        profile.status = FaceProfileStatus.active
        profile.embedding_model = embedding_model.strip() if embedding_model else None
        profile.embedding_version = embedding_version.strip() if embedding_version else None
        profile.revoked_at = None
        profile.revocation_reason = None
        try:
            await self.db.commit()
            await self.db.refresh(profile)
            return profile
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to activate face profile: profile_id=%s", profile_id)
            raise DatabaseException("Failed to activate face profile") from exc


def get_face_profile_repo(db: AsyncSession = Depends(get_db)) -> FaceProfileRepo:
    return FaceProfileRepo(db)
