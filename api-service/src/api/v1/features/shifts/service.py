from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import Depends
from pydantic import ValidationError as PydanticValidationError

from src.api.v1.features.shifts import schemas
from src.api.v1.features.shifts.repo import WorkShiftRepo, get_work_shift_repo
from src.utils.exeptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class WorkShiftService:
    def __init__(self, work_shift_repo: WorkShiftRepo):
        self.work_shift_repo = work_shift_repo

    @staticmethod
    def _to_read(shift) -> schemas.WorkShiftRead:
        return schemas.WorkShiftRead.model_validate(shift)

    @staticmethod
    def _validate_update_time_window(existing, payload: schemas.WorkShiftUpdate) -> None:
        start_time = payload.start_time if payload.start_time is not None else existing.start_time
        end_time = payload.end_time if payload.end_time is not None else existing.end_time
        is_overnight = (
            payload.is_overnight
            if payload.is_overnight is not None
            else existing.is_overnight
        )

        try:
            schemas.WorkShiftBase(
                name=payload.name if payload.name is not None else existing.name,
                code=payload.code if payload.code is not None else existing.code,
                start_time=start_time,
                end_time=end_time,
                is_overnight=is_overnight,
                late_threshold_minutes=(
                    payload.late_threshold_minutes
                    if payload.late_threshold_minutes is not None
                    else existing.late_threshold_minutes
                ),
                early_leave_threshold_minutes=(
                    payload.early_leave_threshold_minutes
                    if payload.early_leave_threshold_minutes is not None
                    else existing.early_leave_threshold_minutes
                ),
                required_work_minutes=(
                    payload.required_work_minutes
                    if payload.required_work_minutes is not None
                    else existing.required_work_minutes
                ),
                is_active=(
                    payload.is_active
                    if payload.is_active is not None
                    else existing.is_active
                ),
            )
        except (ValueError, PydanticValidationError) as exc:
            raise ValidationException(str(exc)) from exc

    async def create_work_shift(self, payload: schemas.WorkShiftCreate) -> schemas.WorkShiftRead:
        logger.info("Create work shift request: name=%s code=%s", payload.name, payload.code)

        if await self.work_shift_repo.name_exists(payload.name):
            logger.warning("Create work shift conflict name: name=%s", payload.name)
            raise ConflictException("Work shift name already exists")
        if await self.work_shift_repo.code_exists(payload.code):
            logger.warning("Create work shift conflict code: code=%s", payload.code)
            raise ConflictException("Work shift code already exists")

        shift = await self.work_shift_repo.create_work_shift(payload)
        logger.info("Work shift created: shift_id=%s name=%s", shift.shift_id, shift.name)
        return self._to_read(shift)

    async def get_work_shift(self, shift_id: int) -> schemas.WorkShiftRead:
        shift = await self.work_shift_repo.get_by_id(shift_id)
        if shift is None:
            logger.warning("Work shift not found: shift_id=%s", shift_id)
            raise NotFoundException("Work shift")
        return self._to_read(shift)

    async def list_work_shifts(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        code: str | None = None,
    ) -> list[schemas.WorkShiftRead]:
        shifts = await self.work_shift_repo.list_work_shifts(
            search=search,
            is_active=is_active,
            code=code,
        )
        logger.info(
            "List work shifts: search=%s is_active=%s code=%s count=%s",
            search,
            is_active,
            code,
            len(shifts),
        )
        return [self._to_read(shift) for shift in shifts]

    async def update_work_shift(
        self,
        shift_id: int,
        payload: schemas.WorkShiftUpdate,
    ) -> schemas.WorkShiftRead:
        shift = await self.work_shift_repo.get_by_id(shift_id)
        if shift is None:
            logger.warning("Update work shift not found: shift_id=%s", shift_id)
            raise NotFoundException("Work shift")

        self._validate_update_time_window(shift, payload)

        if payload.name and await self.work_shift_repo.name_exists(
            payload.name,
            exclude_shift_id=shift_id,
        ):
            logger.warning(
                "Update work shift conflict name: shift_id=%s name=%s",
                shift_id,
                payload.name,
            )
            raise ConflictException("Work shift name already exists")
        if payload.code and await self.work_shift_repo.code_exists(
            payload.code,
            exclude_shift_id=shift_id,
        ):
            logger.warning(
                "Update work shift conflict code: shift_id=%s code=%s",
                shift_id,
                payload.code,
            )
            raise ConflictException("Work shift code already exists")

        updated = await self.work_shift_repo.update_work_shift(shift_id, payload)
        logger.info("Work shift updated: shift_id=%s", shift_id)
        return self._to_read(updated)

    async def set_work_shift_active(
        self,
        shift_id: int,
        is_active: bool,
    ) -> schemas.WorkShiftRead:
        shift = await self.work_shift_repo.get_by_id(shift_id)
        if shift is None:
            logger.warning("Toggle work shift not found: shift_id=%s", shift_id)
            raise NotFoundException("Work shift")

        updated = await self.work_shift_repo.update_work_shift(
            shift_id,
            schemas.WorkShiftUpdate(is_active=is_active),
        )
        logger.info("Work shift active changed: shift_id=%s is_active=%s", shift_id, is_active)
        return self._to_read(updated)

    async def delete_work_shift(self, shift_id: int) -> None:
        shift = await self.work_shift_repo.get_by_id(shift_id)
        if shift is None:
            logger.warning("Delete work shift not found: shift_id=%s", shift_id)
            raise NotFoundException("Work shift")

        await self.work_shift_repo.delete_work_shift(shift_id)
        logger.info("Work shift deleted: shift_id=%s", shift_id)

    @staticmethod
    def _assignment_to_read(assignment) -> schemas.EmployeeShiftAssignmentRead:
        return schemas.EmployeeShiftAssignmentRead.model_validate(assignment)

    @staticmethod
    def _current_shift_to_read(assignment) -> schemas.CurrentShiftRead:
        return schemas.CurrentShiftRead(
            assignment_id=assignment.assignment_id,
            employee_id=assignment.employee_id,
            effective_date=assignment.effective_date,
            end_date=assignment.end_date,
            shift=schemas.WorkShiftRead.model_validate(assignment.shift),
        )

    async def _validate_employee_exists(self, employee_id: uuid.UUID) -> None:
        if not await self.work_shift_repo.employee_exists(employee_id):
            logger.warning("Employee not found for shift assignment: employee_id=%s", employee_id)
            raise NotFoundException("Employee")

    async def _validate_shift_active(self, shift_id: int) -> None:
        if not await self.work_shift_repo.shift_exists_active(shift_id):
            logger.warning("Active work shift not found: shift_id=%s", shift_id)
            raise BadRequestException("Work shift not found or inactive")

    async def create_shift_assignment(
        self,
        employee_id: uuid.UUID,
        payload: schemas.EmployeeShiftAssignmentCreateForEmployee,
        created_by: uuid.UUID | None,
    ) -> schemas.EmployeeShiftAssignmentRead:
        logger.info(
            "Create shift assignment request: employee_id=%s shift_id=%s effective_date=%s end_date=%s created_by=%s",
            employee_id,
            payload.shift_id,
            payload.effective_date,
            payload.end_date,
            created_by,
        )
        await self._validate_employee_exists(employee_id)
        await self._validate_shift_active(payload.shift_id)

        if await self.work_shift_repo.assignment_overlaps(
            employee_id=employee_id,
            effective_date=payload.effective_date,
            end_date=payload.end_date,
        ):
            logger.warning("Shift assignment overlap: employee_id=%s", employee_id)
            raise ConflictException("Shift assignment overlaps existing assignment")

        assignment = await self.work_shift_repo.create_shift_assignment(
            employee_id=employee_id,
            payload=payload,
            created_by=created_by,
        )
        logger.info(
            "Shift assignment created: assignment_id=%s employee_id=%s shift_id=%s",
            assignment.assignment_id,
            employee_id,
            payload.shift_id,
        )
        return self._assignment_to_read(assignment)

    async def list_employee_shift_assignments(
        self,
        employee_id: uuid.UUID,
    ) -> list[schemas.EmployeeShiftAssignmentRead]:
        await self._validate_employee_exists(employee_id)
        assignments = await self.work_shift_repo.list_employee_shift_assignments(employee_id)
        logger.info(
            "List employee shift assignments: employee_id=%s count=%s",
            employee_id,
            len(assignments),
        )
        return [self._assignment_to_read(assignment) for assignment in assignments]

    async def get_current_shift(
        self,
        employee_id: uuid.UUID,
        as_of: date | None = None,
    ) -> schemas.CurrentShiftRead:
        await self._validate_employee_exists(employee_id)
        current_date = as_of or date.today()
        assignment = await self.work_shift_repo.get_current_shift_assignment(
            employee_id=employee_id,
            as_of=current_date,
        )
        if assignment is None:
            logger.warning(
                "Current shift not found: employee_id=%s as_of=%s",
                employee_id,
                current_date,
            )
            raise NotFoundException("Current shift")
        return self._current_shift_to_read(assignment)

    async def update_shift_assignment(
        self,
        assignment_id: int,
        payload: schemas.EmployeeShiftAssignmentUpdate,
    ) -> schemas.EmployeeShiftAssignmentRead:
        assignment = await self.work_shift_repo.get_assignment_by_id(assignment_id)
        if assignment is None:
            logger.warning("Update shift assignment not found: assignment_id=%s", assignment_id)
            raise NotFoundException("Shift assignment")

        new_shift_id = payload.shift_id if payload.shift_id is not None else assignment.shift_id
        new_effective_date = (
            payload.effective_date
            if payload.effective_date is not None
            else assignment.effective_date
        )
        new_end_date = (
            payload.end_date
            if "end_date" in payload.model_fields_set
            else assignment.end_date
        )

        if new_end_date is not None and new_end_date < new_effective_date:
            raise ValidationException("end_date must be on/after effective_date")

        if payload.shift_id is not None:
            await self._validate_shift_active(new_shift_id)

        if await self.work_shift_repo.assignment_overlaps(
            employee_id=assignment.employee_id,
            effective_date=new_effective_date,
            end_date=new_end_date,
            exclude_assignment_id=assignment_id,
        ):
            logger.warning(
                "Update shift assignment overlap: assignment_id=%s employee_id=%s",
                assignment_id,
                assignment.employee_id,
            )
            raise ConflictException("Shift assignment overlaps existing assignment")

        updated = await self.work_shift_repo.update_shift_assignment(assignment_id, payload)
        logger.info("Shift assignment updated: assignment_id=%s", assignment_id)
        return self._assignment_to_read(updated)

    async def close_shift_assignment(
        self,
        assignment_id: int,
        closed_at: date | None = None,
    ) -> schemas.EmployeeShiftAssignmentRead:
        assignment = await self.work_shift_repo.get_assignment_by_id(assignment_id)
        if assignment is None:
            logger.warning("Close shift assignment not found: assignment_id=%s", assignment_id)
            raise NotFoundException("Shift assignment")

        close_date = closed_at or date.today()
        if close_date < assignment.effective_date:
            raise ValidationException("close date must be on/after effective_date")

        updated = await self.work_shift_repo.update_shift_assignment(
            assignment_id,
            schemas.EmployeeShiftAssignmentUpdate(end_date=close_date),
        )
        logger.info(
            "Shift assignment closed: assignment_id=%s end_date=%s",
            assignment_id,
            close_date,
        )
        return self._assignment_to_read(updated)

    async def change_employee_shift(
        self,
        employee_id: uuid.UUID,
        payload: schemas.ChangeShiftPayload,
        created_by: uuid.UUID | None,
    ) -> schemas.EmployeeShiftAssignmentRead:
        logger.info(
            "Change employee shift request: employee_id=%s new_shift_id=%s effective_date=%s created_by=%s reason=%s",
            employee_id,
            payload.new_shift_id,
            payload.effective_date,
            created_by,
            bool(payload.reason),
        )
        await self._validate_employee_exists(employee_id)
        await self._validate_shift_active(payload.new_shift_id)

        current_assignment = await self.work_shift_repo.get_current_shift_assignment(
            employee_id=employee_id,
            as_of=payload.effective_date,
        )

        if current_assignment is None:
            logger.info(
                "No current shift on change date, creating assignment: employee_id=%s effective_date=%s",
                employee_id,
                payload.effective_date,
            )
            return await self.create_shift_assignment(
                employee_id=employee_id,
                payload=schemas.EmployeeShiftAssignmentCreateForEmployee(
                    shift_id=payload.new_shift_id,
                    effective_date=payload.effective_date,
                    end_date=None,
                ),
                created_by=created_by,
            )

        if current_assignment.shift_id == payload.new_shift_id:
            logger.info(
                "Employee already assigned to requested shift: employee_id=%s assignment_id=%s",
                employee_id,
                current_assignment.assignment_id,
            )
            return self._assignment_to_read(current_assignment)

        if current_assignment.effective_date == payload.effective_date:
            logger.info(
                "Changing shift in-place: employee_id=%s assignment_id=%s",
                employee_id,
                current_assignment.assignment_id,
            )
            return await self.update_shift_assignment(
                current_assignment.assignment_id,
                schemas.EmployeeShiftAssignmentUpdate(shift_id=payload.new_shift_id),
            )

        if await self.work_shift_repo.assignment_overlaps(
            employee_id=employee_id,
            effective_date=payload.effective_date,
            end_date=None,
            exclude_assignment_id=current_assignment.assignment_id,
        ):
            logger.warning(
                "Change employee shift overlap: employee_id=%s effective_date=%s",
                employee_id,
                payload.effective_date,
            )
            raise ConflictException("Shift assignment overlaps existing assignment")

        previous_end_date = payload.effective_date - timedelta(days=1)
        await self.work_shift_repo.update_shift_assignment(
            current_assignment.assignment_id,
            schemas.EmployeeShiftAssignmentUpdate(end_date=previous_end_date),
        )

        new_assignment = await self.work_shift_repo.create_shift_assignment(
            employee_id=employee_id,
            payload=schemas.EmployeeShiftAssignmentCreateForEmployee(
                shift_id=payload.new_shift_id,
                effective_date=payload.effective_date,
                end_date=None,
            ),
            created_by=created_by,
        )
        logger.info(
            "Employee shift changed: employee_id=%s previous_assignment_id=%s new_assignment_id=%s",
            employee_id,
            current_assignment.assignment_id,
            new_assignment.assignment_id,
        )
        return self._assignment_to_read(new_assignment)

    async def delete_shift_assignment(self, assignment_id: int) -> None:
        assignment = await self.work_shift_repo.get_assignment_by_id(assignment_id)
        if assignment is None:
            logger.warning("Delete shift assignment not found: assignment_id=%s", assignment_id)
            raise NotFoundException("Shift assignment")

        await self.work_shift_repo.delete_shift_assignment(assignment_id)
        logger.info("Shift assignment deleted: assignment_id=%s", assignment_id)


def get_work_shift_service(
    work_shift_repo: WorkShiftRepo = Depends(get_work_shift_repo),
) -> WorkShiftService:
    return WorkShiftService(work_shift_repo=work_shift_repo)
