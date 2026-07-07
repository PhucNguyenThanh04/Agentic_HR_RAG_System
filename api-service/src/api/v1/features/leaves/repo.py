from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import Depends
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.features.leaves import schemas
from src.api.v1.features.leaves.models import LeaveApprovalLog, LeaveRequest, LeaveType
from src.api.v1.features.shifts.models import Holiday
from src.api.v1.features.staff.models import Employee
from src.api.v1.shared.enums import ApprovalAction, LeaveRequestStatus, RoleName
from src.core.db.database import get_db
from src.utils.exeptions import DatabaseException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class LeaveRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def get_employee_id_by_user_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        try:
            stmt = select(Employee.employee_id).where(Employee.user_id == user_id)
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception("Failed to get employee by user: user_id=%s", user_id)
            raise DatabaseException("Failed to get employee") from exc

    async def employee_exists(self, employee_id: uuid.UUID) -> bool:
        try:
            stmt = select(Employee.employee_id).where(Employee.employee_id == employee_id)
            return (await self.db.execute(stmt)).first() is not None
        except Exception as exc:
            logger.exception("Failed to check employee: employee_id=%s", employee_id)
            raise DatabaseException("Failed to check employee") from exc

    async def leave_type_is_active(self, leave_type_id: int) -> bool:
        try:
            stmt = select(LeaveType.leave_type_id).where(
                LeaveType.leave_type_id == leave_type_id,
                LeaveType.is_active.is_(True),
            )
            return (await self.db.execute(stmt)).first() is not None
        except Exception as exc:
            logger.exception("Failed to check leave type: leave_type_id=%s", leave_type_id)
            raise DatabaseException("Failed to check leave type") from exc

    async def leave_type_name_exists(
        self,
        name: str,
        exclude_leave_type_id: int | None = None,
    ) -> bool:
        try:
            normalized_name = name.strip()
            stmt = select(LeaveType.leave_type_id).where(
                func.lower(LeaveType.name) == normalized_name.lower()
            )
            if exclude_leave_type_id is not None:
                stmt = stmt.where(LeaveType.leave_type_id != exclude_leave_type_id)
            return (await self.db.execute(stmt)).first() is not None
        except Exception as exc:
            logger.exception("Failed to check leave type name: name=%s", name)
            raise DatabaseException("Failed to check leave type name") from exc

    async def leave_type_code_exists(
        self,
        code: str | None,
        exclude_leave_type_id: int | None = None,
    ) -> bool:
        try:
            normalized_code = self._normalize_optional(code)
            if normalized_code is None:
                return False
            stmt = select(LeaveType.leave_type_id).where(LeaveType.code == normalized_code)
            if exclude_leave_type_id is not None:
                stmt = stmt.where(LeaveType.leave_type_id != exclude_leave_type_id)
            return (await self.db.execute(stmt)).first() is not None
        except Exception as exc:
            logger.exception("Failed to check leave type code: code=%s", code)
            raise DatabaseException("Failed to check leave type code") from exc

    async def get_leave_type_by_id(self, leave_type_id: int) -> LeaveType | None:
        try:
            stmt = select(LeaveType).where(LeaveType.leave_type_id == leave_type_id)
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception("Failed to get leave type: leave_type_id=%s", leave_type_id)
            raise DatabaseException("Failed to get leave type") from exc

    async def list_leave_types(self) -> list[LeaveType]:
        try:
            stmt = (
                select(LeaveType)
                .where(LeaveType.is_active.is_(True))
                .order_by(LeaveType.name.asc(), LeaveType.leave_type_id.asc())
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            logger.exception("Failed to list leave types")
            raise DatabaseException("Failed to list leave types") from exc

    async def list_leave_balance_items(
        self,
        *,
        employee_id: uuid.UUID,
        year: int,
    ) -> list[tuple[LeaveType, float]]:
        try:
            year_start = date(year, 1, 1)
            year_end = date(year, 12, 31)
            used_days = func.coalesce(func.sum(LeaveRequest.total_days), 0.0).label("used_days")
            stmt = (
                select(LeaveType, used_days)
                .outerjoin(
                    LeaveRequest,
                    and_(
                        LeaveRequest.leave_type_id == LeaveType.leave_type_id,
                        LeaveRequest.employee_id == employee_id,
                        LeaveRequest.status == LeaveRequestStatus.approved,
                        LeaveRequest.start_date <= year_end,
                        LeaveRequest.end_date >= year_start,
                    ),
                )
                .where(LeaveType.is_active.is_(True))
                .group_by(LeaveType.leave_type_id)
                .order_by(LeaveType.name.asc(), LeaveType.leave_type_id.asc())
            )
            result = await self.db.execute(stmt)
            return [(leave_type, float(used or 0)) for leave_type, used in result.all()]
        except Exception as exc:
            logger.exception(
                "Failed to list leave balance: employee_id=%s year=%s",
                employee_id,
                year,
            )
            raise DatabaseException("Failed to list leave balance") from exc

    async def create_leave_type(self, payload: schemas.LeaveTypeCreate) -> LeaveType:
        leave_type = LeaveType(
            name=payload.name.strip(),
            code=self._normalize_optional(payload.code),
            is_paid=payload.is_paid,
            max_days_per_year=payload.max_days_per_year,
            description=payload.description,
            is_active=payload.is_active,
        )
        self.db.add(leave_type)

        try:
            await self.db.commit()
            await self.db.refresh(leave_type)
            return leave_type
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create leave type: name=%s code=%s",
                payload.name,
                payload.code,
            )
            raise DatabaseException("Failed to create leave type") from exc

    async def update_leave_type(
        self,
        leave_type: LeaveType,
        payload: schemas.LeaveTypeUpdate,
    ) -> LeaveType:
        update_data = payload.model_dump(exclude_unset=True)
        changed = False

        if "name" in update_data and update_data["name"] is not None:
            normalized_name = update_data["name"].strip()
            if leave_type.name != normalized_name:
                leave_type.name = normalized_name
                changed = True

        if "code" in update_data:
            normalized_code = self._normalize_optional(update_data["code"])
            if leave_type.code != normalized_code:
                leave_type.code = normalized_code
                changed = True

        for field in ("is_paid", "max_days_per_year", "description", "is_active"):
            if field in update_data and getattr(leave_type, field) != update_data[field]:
                setattr(leave_type, field, update_data[field])
                changed = True

        if changed:
            try:
                await self.db.commit()
                await self.db.refresh(leave_type)
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update leave type: leave_type_id=%s",
                    leave_type.leave_type_id,
                )
                raise DatabaseException("Failed to update leave type") from exc

        return leave_type

    async def list_leave_requests(
        self,
        query: schemas.LeaveRequestListQuery,
    ) -> tuple[list[LeaveRequest], int]:
        try:
            stmt: Select = select(LeaveRequest).options(selectinload(LeaveRequest.leave_type))

            if query.employee_id is not None:
                stmt = stmt.where(LeaveRequest.employee_id == query.employee_id)
            if query.leave_type_id is not None:
                stmt = stmt.where(LeaveRequest.leave_type_id == query.leave_type_id)
            if query.status is not None:
                stmt = stmt.where(LeaveRequest.status == query.status)
            if query.start_from is not None:
                stmt = stmt.where(LeaveRequest.start_date >= query.start_from)
            if query.start_to is not None:
                stmt = stmt.where(LeaveRequest.start_date <= query.start_to)

            count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
            total = int((await self.db.scalar(count_stmt)) or 0)

            stmt = stmt.order_by(LeaveRequest.created_at.desc())
            stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
            result = await self.db.execute(stmt)
            return list(result.scalars().all()), total
        except Exception as exc:
            logger.exception("Failed to list leave requests")
            raise DatabaseException("Failed to list leave requests") from exc

    async def list_holiday_dates(self, start_date: date, end_date: date) -> set[date]:
        try:
            stmt = select(Holiday.holiday_date).where(
                Holiday.holiday_date >= start_date,
                Holiday.holiday_date <= end_date,
            )
            result = await self.db.execute(stmt)
            return set(result.scalars().all())
        except Exception as exc:
            logger.exception(
                "Failed to list holidays for leave calculation: start_date=%s end_date=%s",
                start_date,
                end_date,
            )
            raise DatabaseException("Failed to list holidays") from exc

    async def has_overlapping_active_request(
        self,
        *,
        employee_id: uuid.UUID,
        start_date: date,
        end_date: date,
        exclude_request_id: uuid.UUID | None = None,
    ) -> bool:
        try:
            stmt = select(LeaveRequest.request_id).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status.in_(
                    [
                        LeaveRequestStatus.pending,
                        LeaveRequestStatus.approved,
                    ]
                ),
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
            if exclude_request_id is not None:
                stmt = stmt.where(LeaveRequest.request_id != exclude_request_id)
            return (await self.db.execute(stmt)).first() is not None
        except Exception as exc:
            logger.exception(
                "Failed to check overlapping leave request: employee_id=%s start_date=%s end_date=%s",
                employee_id,
                start_date,
                end_date,
            )
            raise DatabaseException("Failed to check overlapping leave request") from exc

    async def create_leave_request(
        self,
        *,
        employee_id: uuid.UUID,
        payload: schemas.LeaveRequestCreate,
        total_days: float,
    ) -> LeaveRequest:
        leave_request = LeaveRequest(
            employee_id=employee_id,
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            time_type=payload.time_type,
            total_days=total_days,
            reason=payload.reason,
            status=LeaveRequestStatus.pending,
        )
        self.db.add(leave_request)

        try:
            await self.db.commit()
            await self.db.refresh(leave_request)
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create leave request: employee_id=%s leave_type_id=%s",
                employee_id,
                payload.leave_type_id,
            )
            raise DatabaseException("Failed to create leave request") from exc

        created = await self.get_leave_request_by_id(leave_request.request_id)
        if created is None:
            raise DatabaseException("Failed to reload created leave request")
        return created

    async def get_leave_request_by_id(self, request_id: uuid.UUID) -> LeaveRequest | None:
        try:
            stmt: Select = (
                select(LeaveRequest)
                .options(selectinload(LeaveRequest.leave_type))
                .where(LeaveRequest.request_id == request_id)
            )
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception("Failed to get leave request: request_id=%s", request_id)
            raise DatabaseException("Failed to get leave request") from exc

    async def list_leave_approval_logs(
        self,
        request_id: uuid.UUID,
    ) -> list[LeaveApprovalLog]:
        try:
            stmt = (
                select(LeaveApprovalLog)
                .where(LeaveApprovalLog.leave_request_id == request_id)
                .order_by(LeaveApprovalLog.created_at.asc(), LeaveApprovalLog.log_id.asc())
            )
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            logger.exception("Failed to list leave approval logs: request_id=%s", request_id)
            raise DatabaseException("Failed to list leave approval logs") from exc

    async def update_leave_request(
        self,
        leave_request: LeaveRequest,
        payload: schemas.LeaveRequestUpdate,
        *,
        total_days: float,
    ) -> LeaveRequest:
        update_data = payload.model_dump(exclude_unset=True)
        editable_fields = {
            "leave_type_id",
            "start_date",
            "end_date",
            "time_type",
            "reason",
        }
        changed = False

        for field in editable_fields:
            if field in update_data and getattr(leave_request, field) != update_data[field]:
                setattr(leave_request, field, update_data[field])
                changed = True

        if leave_request.total_days != total_days:
            leave_request.total_days = total_days
            changed = True

        if changed:
            try:
                await self.db.commit()
                await self.db.refresh(leave_request)
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update leave request: request_id=%s",
                    leave_request.request_id,
                )
                raise DatabaseException("Failed to update leave request") from exc

        updated = await self.get_leave_request_by_id(leave_request.request_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated leave request")
        return updated

    async def cancel_leave_request(self, leave_request: LeaveRequest) -> LeaveRequest:
        leave_request.status = LeaveRequestStatus.cancelled
        try:
            await self.db.commit()
            await self.db.refresh(leave_request)
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to cancel leave request: request_id=%s",
                leave_request.request_id,
            )
            raise DatabaseException("Failed to cancel leave request") from exc

        updated = await self.get_leave_request_by_id(leave_request.request_id)
        if updated is None:
            raise DatabaseException("Failed to reload cancelled leave request")
        return updated

    async def review_leave_request(
        self,
        leave_request: LeaveRequest,
        *,
        approver_id: uuid.UUID,
        reviewer_role: RoleName,
        payload: schemas.ReviewLeaveRequest,
    ) -> LeaveRequest:
        now = datetime.now(timezone.utc)
        log = LeaveApprovalLog(
            leave_request_id=leave_request.request_id,
            approver_id=approver_id,
            action=payload.action,
            comment=payload.comment,
        )
        self.db.add(log)

        if payload.action == ApprovalAction.rejected:
            leave_request.status = LeaveRequestStatus.rejected
            leave_request.approved_by = approver_id
            leave_request.approved_at = now
            leave_request.rejection_reason = payload.rejection_reason
        elif reviewer_role in {RoleName.admin, RoleName.hr}:
            leave_request.status = LeaveRequestStatus.approved
            leave_request.approved_by = approver_id
            leave_request.approved_at = now
            leave_request.rejection_reason = None

        try:
            await self.db.commit()
            await self.db.refresh(leave_request)
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to review leave request: request_id=%s approver_id=%s",
                leave_request.request_id,
                approver_id,
            )
            raise DatabaseException("Failed to review leave request") from exc

        updated = await self.get_leave_request_by_id(leave_request.request_id)
        if updated is None:
            raise DatabaseException("Failed to reload reviewed leave request")
        return updated


def get_leave_repo(db: AsyncSession = Depends(get_db)) -> LeaveRepo:
    return LeaveRepo(db)
