from __future__ import annotations

import uuid
from datetime import date

from fastapi import Depends
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.features.staff.models import Employee
from src.api.v1.features.shifts import schemas
from src.api.v1.features.shifts.models import EmployeeShiftAssignment, WorkShift
from src.core.db.database import get_db
from src.utils.exeptions import ConflictException, DatabaseException, NotFoundException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class WorkShiftRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_optional(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    async def name_exists(self, name: str | None, exclude_shift_id: int | None = None) -> bool:
        normalized_name = self._normalize_optional(name)
        if normalized_name is None:
            return False

        stmt = select(WorkShift.shift_id).where(
            func.lower(WorkShift.name) == normalized_name.lower()
        )
        if exclude_shift_id is not None:
            stmt = stmt.where(WorkShift.shift_id != exclude_shift_id)
        return (await self.db.execute(stmt)).first() is not None

    async def code_exists(self, code: str | None, exclude_shift_id: int | None = None) -> bool:
        normalized_code = self._normalize_optional(code)
        if normalized_code is None:
            return False

        stmt = select(WorkShift.shift_id).where(WorkShift.code == normalized_code)
        if exclude_shift_id is not None:
            stmt = stmt.where(WorkShift.shift_id != exclude_shift_id)
        return (await self.db.execute(stmt)).first() is not None

    async def get_by_id(self, shift_id: int) -> WorkShift | None:
        return await self.db.scalar(select(WorkShift).where(WorkShift.shift_id == shift_id))

    async def get_or_404(self, shift_id: int) -> WorkShift:
        shift = await self.get_by_id(shift_id)
        if shift is None:
            raise NotFoundException("Work shift")
        return shift

    async def list_work_shifts(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        code: str | None = None,
    ) -> list[WorkShift]:
        stmt: Select = select(WorkShift)

        if is_active is not None:
            stmt = stmt.where(WorkShift.is_active.is_(is_active))

        normalized_code = self._normalize_optional(code)
        if normalized_code is not None:
            stmt = stmt.where(WorkShift.code == normalized_code)

        if search:
            term = search.strip().lower()
            if term:
                stmt = stmt.where(func.lower(WorkShift.name).like(f"%{term}%"))

        result = await self.db.execute(stmt.order_by(WorkShift.start_time, WorkShift.name))
        return list(result.scalars().all())

    async def create_work_shift(self, payload: schemas.WorkShiftCreate) -> WorkShift:
        normalized_name = payload.name.strip()
        normalized_code = self._normalize_optional(payload.code)

        if await self.name_exists(normalized_name):
            raise ConflictException("Work shift name already exists")
        if await self.code_exists(normalized_code):
            raise ConflictException("Work shift code already exists")

        shift = WorkShift(
            name=normalized_name,
            code=normalized_code,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_overnight=payload.is_overnight,
            late_threshold_minutes=payload.late_threshold_minutes,
            early_leave_threshold_minutes=payload.early_leave_threshold_minutes,
            required_work_minutes=payload.required_work_minutes,
            is_active=payload.is_active,
        )
        self.db.add(shift)

        try:
            await self.db.commit()
            await self.db.refresh(shift)
            return shift
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create work shift: name=%s code=%s",
                normalized_name,
                normalized_code,
            )
            raise DatabaseException("Failed to create work shift") from exc

    async def update_work_shift(
        self,
        shift_id: int,
        payload: schemas.WorkShiftUpdate,
    ) -> WorkShift:
        shift = await self.get_or_404(shift_id)
        changed = False

        if payload.name is not None:
            normalized_name = payload.name.strip()
            if normalized_name != shift.name:
                if await self.name_exists(normalized_name, exclude_shift_id=shift_id):
                    raise ConflictException("Work shift name already exists")
                shift.name = normalized_name
                changed = True

        if payload.code is not None:
            normalized_code = payload.code.strip()
            if normalized_code != shift.code:
                if await self.code_exists(normalized_code, exclude_shift_id=shift_id):
                    raise ConflictException("Work shift code already exists")
                shift.code = normalized_code
                changed = True
        elif "code" in payload.model_fields_set and shift.code is not None:
            shift.code = None
            changed = True

        for field in (
            "start_time",
            "end_time",
            "is_overnight",
            "late_threshold_minutes",
            "early_leave_threshold_minutes",
            "required_work_minutes",
            "is_active",
        ):
            value = getattr(payload, field)
            if value is not None and value != getattr(shift, field):
                setattr(shift, field, value)
                changed = True
            elif (
                field == "required_work_minutes"
                and field in payload.model_fields_set
                and getattr(shift, field) is not None
            ):
                shift.required_work_minutes = None
                changed = True

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.exception("Failed to update work shift: shift_id=%s", shift_id)
                raise DatabaseException("Failed to update work shift") from exc

        updated = await self.get_by_id(shift_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated work shift")
        return updated

    async def delete_work_shift(self, shift_id: int) -> None:
        shift = await self.get_or_404(shift_id)

        try:
            await self.db.delete(shift)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to delete work shift: shift_id=%s", shift_id)
            raise DatabaseException("Failed to delete work shift") from exc

    async def employee_exists(self, employee_id: uuid.UUID) -> bool:
        stmt = select(Employee.employee_id).where(Employee.employee_id == employee_id)
        return (await self.db.execute(stmt)).first() is not None

    async def shift_exists_active(self, shift_id: int) -> bool:
        stmt = select(WorkShift.shift_id).where(
            WorkShift.shift_id == shift_id,
            WorkShift.is_active.is_(True),
        )
        return (await self.db.execute(stmt)).first() is not None

    async def get_assignment_by_id(
        self,
        assignment_id: int,
    ) -> EmployeeShiftAssignment | None:
        stmt = (
            select(EmployeeShiftAssignment)
            .options(selectinload(EmployeeShiftAssignment.shift))
            .where(EmployeeShiftAssignment.assignment_id == assignment_id)
        )
        return await self.db.scalar(stmt)

    async def get_assignment_or_404(self, assignment_id: int) -> EmployeeShiftAssignment:
        assignment = await self.get_assignment_by_id(assignment_id)
        if assignment is None:
            raise NotFoundException("Shift assignment")
        return assignment

    async def assignment_overlaps(
        self,
        employee_id: uuid.UUID,
        effective_date: date,
        end_date: date | None,
        exclude_assignment_id: int | None = None,
    ) -> bool:
        stmt = select(EmployeeShiftAssignment.assignment_id).where(
            EmployeeShiftAssignment.employee_id == employee_id,
            or_(
                EmployeeShiftAssignment.end_date.is_(None),
                EmployeeShiftAssignment.end_date >= effective_date,
            ),
        )
        if end_date is not None:
            stmt = stmt.where(EmployeeShiftAssignment.effective_date <= end_date)
        if exclude_assignment_id is not None:
            stmt = stmt.where(
                EmployeeShiftAssignment.assignment_id != exclude_assignment_id
            )
        return (await self.db.execute(stmt)).first() is not None

    async def create_shift_assignment(
        self,
        employee_id: uuid.UUID,
        payload: schemas.EmployeeShiftAssignmentCreateForEmployee,
        created_by: uuid.UUID | None,
    ) -> EmployeeShiftAssignment:
        assignment = EmployeeShiftAssignment(
            employee_id=employee_id,
            shift_id=payload.shift_id,
            effective_date=payload.effective_date,
            end_date=payload.end_date,
            created_by=created_by,
        )
        self.db.add(assignment)

        try:
            await self.db.commit()
            await self.db.refresh(assignment)
            return await self.get_assignment_or_404(assignment.assignment_id)
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to create shift assignment: employee_id=%s shift_id=%s",
                employee_id,
                payload.shift_id,
            )
            raise DatabaseException("Failed to create shift assignment") from exc

    async def list_employee_shift_assignments(
        self,
        employee_id: uuid.UUID,
    ) -> list[EmployeeShiftAssignment]:
        stmt = (
            select(EmployeeShiftAssignment)
            .options(selectinload(EmployeeShiftAssignment.shift))
            .where(EmployeeShiftAssignment.employee_id == employee_id)
            .order_by(
                EmployeeShiftAssignment.effective_date.desc(),
                EmployeeShiftAssignment.assignment_id.desc(),
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_current_shift_assignment(
        self,
        employee_id: uuid.UUID,
        as_of: date,
    ) -> EmployeeShiftAssignment | None:
        stmt = (
            select(EmployeeShiftAssignment)
            .options(selectinload(EmployeeShiftAssignment.shift))
            .where(
                EmployeeShiftAssignment.employee_id == employee_id,
                EmployeeShiftAssignment.effective_date <= as_of,
                or_(
                    EmployeeShiftAssignment.end_date.is_(None),
                    EmployeeShiftAssignment.end_date >= as_of,
                ),
            )
            .order_by(
                EmployeeShiftAssignment.effective_date.desc(),
                EmployeeShiftAssignment.assignment_id.desc(),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def update_shift_assignment(
        self,
        assignment_id: int,
        payload: schemas.EmployeeShiftAssignmentUpdate,
    ) -> EmployeeShiftAssignment:
        assignment = await self.get_assignment_or_404(assignment_id)
        changed = False

        if payload.shift_id is not None and payload.shift_id != assignment.shift_id:
            assignment.shift_id = payload.shift_id
            changed = True

        if (
            payload.effective_date is not None
            and payload.effective_date != assignment.effective_date
        ):
            assignment.effective_date = payload.effective_date
            changed = True

        if "end_date" in payload.model_fields_set and payload.end_date != assignment.end_date:
            assignment.end_date = payload.end_date
            changed = True

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update shift assignment: assignment_id=%s",
                    assignment_id,
                )
                raise DatabaseException("Failed to update shift assignment") from exc

        return await self.get_assignment_or_404(assignment_id)

    async def delete_shift_assignment(self, assignment_id: int) -> None:
        assignment = await self.get_assignment_or_404(assignment_id)

        try:
            await self.db.delete(assignment)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.exception(
                "Failed to delete shift assignment: assignment_id=%s",
                assignment_id,
            )
            raise DatabaseException("Failed to delete shift assignment") from exc


def get_work_shift_repo(db: AsyncSession = Depends(get_db)) -> WorkShiftRepo:
    return WorkShiftRepo(db)
