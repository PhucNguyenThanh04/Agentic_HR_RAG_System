from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import Depends

from src.api.v1.features.leaves import schemas
from src.api.v1.features.leaves.repo import LeaveRepo, get_leave_repo
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import ApprovalAction, LeaveRequestStatus, LeaveTimeType, RoleName
from src.utils.exeptions import (
    AppException,
    ConflictException,
    DatabaseException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class LeaveService:
    def __init__(self, leave_repo: LeaveRepo):
        self.leave_repo = leave_repo

    @staticmethod
    def _to_read(leave_request) -> schemas.LeaveRequestRead:
        return schemas.LeaveRequestRead.model_validate(leave_request)

    @staticmethod
    def _leave_type_to_read(leave_type) -> schemas.LeaveTypeRead:
        return schemas.LeaveTypeRead.model_validate(leave_type)

    @staticmethod
    def _date_range(start_date: date, end_date: date):
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)

    async def calculate_leave_days(self, payload: schemas.LeaveRequestCreate) -> float:
        if payload.time_type in {LeaveTimeType.morning, LeaveTimeType.afternoon}:
            return 0.5
        if payload.time_type == LeaveTimeType.custom:
            if payload.total_days is None:
                raise ValidationException("total_days is required when time_type=custom")
            return payload.total_days

        holidays = await self.leave_repo.list_holiday_dates(
            payload.start_date,
            payload.end_date,
        )
        working_days = sum(
            1
            for day in self._date_range(payload.start_date, payload.end_date)
            if day.weekday() < 5 and day not in holidays
        )
        if working_days <= 0:
            raise ValidationException("Leave request must include at least one working day")
        return float(working_days)

    async def list_leave_types(self) -> list[schemas.LeaveTypeRead]:
        try:
            leave_types = await self.leave_repo.list_leave_types()
            return [self._leave_type_to_read(leave_type) for leave_type in leave_types]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to list leave types")
            raise DatabaseException("Failed to list leave types") from exc

    async def create_leave_type(
        self,
        payload: schemas.LeaveTypeCreate,
    ) -> schemas.LeaveTypeRead:
        try:
            if await self.leave_repo.leave_type_name_exists(payload.name):
                raise ConflictException("Leave type name already exists")
            if await self.leave_repo.leave_type_code_exists(payload.code):
                raise ConflictException("Leave type code already exists")

            leave_type = await self.leave_repo.create_leave_type(payload)
            logger.info("Leave type created: leave_type_id=%s", leave_type.leave_type_id)
            return self._leave_type_to_read(leave_type)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to create leave type")
            raise DatabaseException("Failed to create leave type") from exc

    async def update_leave_type(
        self,
        leave_type_id: int,
        payload: schemas.LeaveTypeUpdate,
    ) -> schemas.LeaveTypeRead:
        try:
            leave_type = await self.leave_repo.get_leave_type_by_id(leave_type_id)
            if leave_type is None:
                logger.warning("Leave type not found for update: leave_type_id=%s", leave_type_id)
                raise NotFoundException("Leave type")

            if payload.name is not None and await self.leave_repo.leave_type_name_exists(
                payload.name,
                exclude_leave_type_id=leave_type_id,
            ):
                raise ConflictException("Leave type name already exists")

            if "code" in payload.model_fields_set and await self.leave_repo.leave_type_code_exists(
                payload.code,
                exclude_leave_type_id=leave_type_id,
            ):
                raise ConflictException("Leave type code already exists")

            updated = await self.leave_repo.update_leave_type(leave_type, payload)
            logger.info("Leave type updated: leave_type_id=%s", leave_type_id)
            return self._leave_type_to_read(updated)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to update leave type: leave_type_id=%s", leave_type_id)
            raise DatabaseException("Failed to update leave type") from exc

    async def get_leave_balance(
        self,
        *,
        employee_id: uuid.UUID,
        current_user: User,
        year: int | None = None,
    ) -> schemas.LeaveBalanceRead:
        try:
            balance_year = year or date.today().year
            if balance_year < 1900 or balance_year > 9999:
                raise ValidationException("year must be between 1900 and 9999")

            if current_user.role_name == RoleName.employee:
                current_employee_id = await self.leave_repo.get_employee_id_by_user_id(
                    current_user.user_id
                )
                if current_employee_id is None:
                    raise NotFoundException("Employee profile")
                if current_employee_id != employee_id:
                    raise ForbiddenException("You can only view your own leave balance")

            if not await self.leave_repo.employee_exists(employee_id):
                raise NotFoundException("Employee")

            balance_rows = await self.leave_repo.list_leave_balance_items(
                employee_id=employee_id,
                year=balance_year,
            )

            items: list[schemas.LeaveBalanceItem] = []
            total_allowed_days = 0.0
            total_used_days = 0.0
            total_remaining_days = 0.0

            for leave_type, used_days in balance_rows:
                total_used_days += used_days
                remaining_days: float | None = None
                if leave_type.max_days_per_year is not None:
                    allowed_days = float(leave_type.max_days_per_year)
                    remaining_days = allowed_days - used_days
                    total_allowed_days += allowed_days
                    total_remaining_days += remaining_days

                items.append(
                    schemas.LeaveBalanceItem(
                        leave_type_id=leave_type.leave_type_id,
                        name=leave_type.name,
                        code=leave_type.code,
                        is_paid=leave_type.is_paid,
                        max_days_per_year=leave_type.max_days_per_year,
                        used_days=used_days,
                        remaining_days=remaining_days,
                    )
                )

            return schemas.LeaveBalanceRead(
                employee_id=employee_id,
                year=balance_year,
                total_allowed_days=total_allowed_days,
                total_used_days=total_used_days,
                total_remaining_days=total_remaining_days,
                items=items,
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception(
                "Failed to get leave balance: employee_id=%s year=%s",
                employee_id,
                year,
            )
            raise DatabaseException("Failed to get leave balance") from exc

    async def create_leave_request(
        self,
        *,
        employee_id: uuid.UUID,
        payload: schemas.LeaveRequestCreate,
    ) -> schemas.LeaveRequestRead:
        try:
            if not await self.leave_repo.leave_type_is_active(payload.leave_type_id):
                logger.warning(
                    "Leave type not found or inactive: leave_type_id=%s",
                    payload.leave_type_id,
                )
                raise NotFoundException("Leave type")

            if await self.leave_repo.has_overlapping_active_request(
                employee_id=employee_id,
                start_date=payload.start_date,
                end_date=payload.end_date,
            ):
                logger.warning(
                    "Overlapping leave request: employee_id=%s start_date=%s end_date=%s",
                    employee_id,
                    payload.start_date,
                    payload.end_date,
                )
                raise ConflictException("Leave request overlaps an existing request")

            total_days = await self.calculate_leave_days(payload)
            leave_request = await self.leave_repo.create_leave_request(
                employee_id=employee_id,
                payload=payload,
                total_days=total_days,
            )
            logger.info(
                "Leave request created: request_id=%s employee_id=%s",
                leave_request.request_id,
                employee_id,
            )
            return self._to_read(leave_request)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to create leave request: employee_id=%s", employee_id)
            raise DatabaseException("Failed to create leave request") from exc

    async def list_leave_requests(
        self,
        *,
        query: schemas.LeaveRequestListQuery,
        current_user: User,
    ) -> schemas.LeaveRequestListResponse:
        try:
            effective_query = query
            if current_user.role_name == RoleName.employee:
                employee_id = await self.leave_repo.get_employee_id_by_user_id(current_user.user_id)
                if employee_id is None:
                    raise NotFoundException("Employee profile")
                effective_query = query.model_copy(update={"employee_id": employee_id})

            leave_requests, total = await self.leave_repo.list_leave_requests(effective_query)
            return schemas.LeaveRequestListResponse(
                items=[self._to_read(leave_request) for leave_request in leave_requests],
                total=total,
                page=effective_query.page,
                page_size=effective_query.page_size,
            )
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to list leave requests")
            raise DatabaseException("Failed to list leave requests") from exc

    async def get_leave_request(self, request_id: uuid.UUID) -> schemas.LeaveRequestRead:
        try:
            leave_request = await self.leave_repo.get_leave_request_by_id(request_id)
            if leave_request is None:
                logger.warning("Leave request not found: request_id=%s", request_id)
                raise NotFoundException("Leave request")
            return self._to_read(leave_request)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to get leave request: request_id=%s", request_id)
            raise DatabaseException("Failed to get leave request") from exc

    async def update_pending_leave_request(
        self,
        request_id: uuid.UUID,
        payload: schemas.LeaveRequestUpdate,
        employee_id: uuid.UUID,
    ) -> schemas.LeaveRequestRead:
        try:
            leave_request = await self.leave_repo.get_leave_request_by_id(request_id)
            if leave_request is None:
                logger.warning("Leave request not found for update: request_id=%s", request_id)
                raise NotFoundException("Leave request")
            if leave_request.employee_id != employee_id:
                raise ForbiddenException("You can only update your own leave request")
            if leave_request.status != LeaveRequestStatus.pending:
                raise ConflictException("Only pending leave requests can be updated")

            forbidden_fields = {
                "status",
                "approved_by",
                "approved_at",
                "rejection_reason",
            }
            touched_forbidden_fields = forbidden_fields.intersection(payload.model_fields_set)
            if touched_forbidden_fields:
                raise ValidationException(
                    f"{', '.join(sorted(touched_forbidden_fields))} cannot be updated here"
                )

            leave_type_id = payload.leave_type_id or leave_request.leave_type_id
            if payload.leave_type_id is not None and not await self.leave_repo.leave_type_is_active(
                payload.leave_type_id
            ):
                raise NotFoundException("Leave type")

            start_date = payload.start_date or leave_request.start_date
            end_date = payload.end_date or leave_request.end_date
            time_type = payload.time_type or leave_request.time_type
            total_days = (
                payload.total_days
                if "total_days" in payload.model_fields_set
                else leave_request.total_days
            )
            effective_payload = schemas.LeaveRequestCreate(
                leave_type_id=leave_type_id,
                start_date=start_date,
                end_date=end_date,
                time_type=time_type,
                total_days=total_days,
                reason=(
                    payload.reason
                    if "reason" in payload.model_fields_set
                    else leave_request.reason
                ),
            )

            if await self.leave_repo.has_overlapping_active_request(
                employee_id=leave_request.employee_id,
                start_date=start_date,
                end_date=end_date,
                exclude_request_id=request_id,
            ):
                raise ConflictException("Leave request overlaps an existing request")

            recalculated_total_days = await self.calculate_leave_days(effective_payload)
            updated = await self.leave_repo.update_leave_request(
                leave_request,
                payload,
                total_days=recalculated_total_days,
            )
            logger.info("Leave request updated: request_id=%s", request_id)
            return self._to_read(updated)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to update leave request: request_id=%s", request_id)
            raise DatabaseException("Failed to update leave request") from exc

    async def cancel_leave_request(
        self,
        request_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> schemas.LeaveRequestRead:
        try:
            leave_request = await self.leave_repo.get_leave_request_by_id(request_id)
            if leave_request is None:
                logger.warning("Leave request not found for cancel: request_id=%s", request_id)
                raise NotFoundException("Leave request")
            if leave_request.employee_id != employee_id:
                raise ForbiddenException("You can only cancel your own leave request")
            if leave_request.status != LeaveRequestStatus.pending:
                raise ConflictException("Only pending leave requests can be cancelled")

            cancelled = await self.leave_repo.cancel_leave_request(leave_request)
            logger.info(
                "Leave request cancelled: request_id=%s employee_id=%s",
                request_id,
                employee_id,
            )
            return self._to_read(cancelled)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to cancel leave request: request_id=%s", request_id)
            raise DatabaseException("Failed to cancel leave request") from exc

    async def review_leave_request(
        self,
        request_id: uuid.UUID,
        payload: schemas.ReviewLeaveRequest,
        *,
        approver_id: uuid.UUID,
        reviewer_role: RoleName,
    ) -> schemas.LeaveRequestRead:
        try:
            if payload.action not in {ApprovalAction.approved, ApprovalAction.rejected}:
                raise ValidationException("Review action must be approved or rejected")

            leave_request = await self.leave_repo.get_leave_request_by_id(request_id)
            if leave_request is None:
                logger.warning("Leave request not found for review: request_id=%s", request_id)
                raise NotFoundException("Leave request")
            if leave_request.status != LeaveRequestStatus.pending:
                raise ConflictException("Only pending leave requests can be reviewed")

            reviewed = await self.leave_repo.review_leave_request(
                leave_request,
                approver_id=approver_id,
                reviewer_role=reviewer_role,
                payload=payload,
            )
            logger.info(
                "Leave request reviewed: request_id=%s approver_id=%s action=%s",
                request_id,
                approver_id,
                payload.action,
            )
            return self._to_read(reviewed)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to review leave request: request_id=%s", request_id)
            raise DatabaseException("Failed to review leave request") from exc

    async def list_leave_request_logs(
        self,
        request_id: uuid.UUID,
        current_user: User,
    ) -> list[schemas.LeaveApprovalLogRead]:
        try:
            leave_request = await self.leave_repo.get_leave_request_by_id(request_id)
            if leave_request is None:
                logger.warning("Leave request not found for logs: request_id=%s", request_id)
                raise NotFoundException("Leave request")

            if current_user.role_name == RoleName.employee:
                employee_id = await self.leave_repo.get_employee_id_by_user_id(current_user.user_id)
                if employee_id is None:
                    raise NotFoundException("Employee profile")
                if leave_request.employee_id != employee_id:
                    raise ForbiddenException("You can only view logs for your own leave request")

            logs = await self.leave_repo.list_leave_approval_logs(request_id)
            return [schemas.LeaveApprovalLogRead.model_validate(log) for log in logs]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to list leave request logs: request_id=%s", request_id)
            raise DatabaseException("Failed to list leave request logs") from exc


def get_leave_service(
    leave_repo: LeaveRepo = Depends(get_leave_repo),
) -> LeaveService:
    return LeaveService(leave_repo=leave_repo)
