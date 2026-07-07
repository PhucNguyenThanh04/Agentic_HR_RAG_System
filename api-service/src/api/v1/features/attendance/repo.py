from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from fastapi import Depends
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.features.attendance.models import AttendanceEvent, AttendanceRecord
from src.api.v1.features.attendance import schemas
from src.api.v1.features.shifts.models import EmployeeShiftAssignment, WorkShift
from src.api.v1.features.staff.models import Employee
from src.api.v1.shared.enums import AttendanceRecordStatus, AttendanceSource, EmployeeStatus
from src.core.db.database import get_db
from src.utils.exeptions import DatabaseException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class AttendanceRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def work_date_to_db_value(work_date: date) -> datetime:
        # Current schema stores work_date as DateTime, so normalize date to midnight.
        return datetime.combine(work_date, time.min)

    async def employee_exists(self, employee_id: uuid.UUID) -> bool:
        try:
            stmt = select(Employee.employee_id).where(Employee.employee_id == employee_id)
            return (await self.db.execute(stmt)).first() is not None
        except Exception as exc:
            logger.exception("Failed to check employee exists: employee_id=%s", employee_id)
            raise DatabaseException("Failed to check employee exists") from exc

    async def get_employee_status(self, employee_id: uuid.UUID) -> EmployeeStatus | None:
        try:
            stmt = select(Employee.status).where(Employee.employee_id == employee_id)
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception("Failed to get employee status: employee_id=%s", employee_id)
            raise DatabaseException("Failed to get employee status") from exc

    async def get_event_by_id(self, event_id: uuid.UUID) -> AttendanceEvent | None:
        try:
            return await self.db.scalar(
                select(AttendanceEvent).where(AttendanceEvent.event_id == event_id)
            )
        except Exception as exc:
            logger.exception("Failed to get attendance event: event_id=%s", event_id)
            raise DatabaseException("Failed to get attendance event") from exc

    async def list_events(
        self,
        query: schemas.AttendanceEventListQuery,
    ) -> list[AttendanceEvent]:
        try:
            stmt: Select = select(AttendanceEvent)

            if query.employee_id is not None:
                stmt = stmt.where(AttendanceEvent.employee_id == query.employee_id)
            if query.event_type is not None:
                stmt = stmt.where(AttendanceEvent.event_type == query.event_type)
            if query.accepted is not None:
                stmt = stmt.where(AttendanceEvent.is_accepted.is_(query.accepted))
            if query.event_time_from is not None:
                stmt = stmt.where(AttendanceEvent.event_time >= query.event_time_from)
            if query.event_time_to is not None:
                stmt = stmt.where(AttendanceEvent.event_time <= query.event_time_to)

            stmt = stmt.order_by(
                AttendanceEvent.event_time.desc(),
                AttendanceEvent.created_at.desc(),
            )
            stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            logger.exception("Failed to list attendance events")
            raise DatabaseException("Failed to list attendance events") from exc

    async def get_record_by_employee_and_work_date(
        self,
        employee_id: uuid.UUID,
        work_date: date,
    ) -> AttendanceRecord | None:
        try:
            work_date_value = self.work_date_to_db_value(work_date)
            stmt = (
                select(AttendanceRecord)
                .options(selectinload(AttendanceRecord.shift))
                .where(
                    and_(
                        AttendanceRecord.employee_id == employee_id,
                        AttendanceRecord.work_date == work_date_value,
                    )
                )
            )
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception(
                "Failed to get attendance record: employee_id=%s work_date=%s",
                employee_id,
                work_date,
            )
            raise DatabaseException("Failed to get attendance record") from exc

    async def get_record_by_id(self, record_id: uuid.UUID) -> AttendanceRecord | None:
        try:
            return await self.db.scalar(
                select(AttendanceRecord)
                .options(selectinload(AttendanceRecord.shift))
                .where(AttendanceRecord.record_id == record_id)
            )
        except Exception as exc:
            logger.exception("Failed to get attendance record: record_id=%s", record_id)
            raise DatabaseException("Failed to get attendance record") from exc

    async def get_current_shift_assignment(
        self,
        employee_id: uuid.UUID,
        as_of: date,
    ) -> EmployeeShiftAssignment | None:
        try:
            stmt = (
                select(EmployeeShiftAssignment)
                .join(WorkShift, EmployeeShiftAssignment.shift_id == WorkShift.shift_id)
                .options(selectinload(EmployeeShiftAssignment.shift))
                .where(
                    EmployeeShiftAssignment.employee_id == employee_id,
                    EmployeeShiftAssignment.effective_date <= as_of,
                    WorkShift.is_active.is_(True),
                    (
                        (EmployeeShiftAssignment.end_date.is_(None))
                        | (EmployeeShiftAssignment.end_date >= as_of)
                    ),
                )
                .order_by(
                    EmployeeShiftAssignment.effective_date.desc(),
                    EmployeeShiftAssignment.assignment_id.desc(),
                )
                .limit(1)
            )
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception(
                "Failed to get current shift assignment: employee_id=%s as_of=%s",
                employee_id,
                as_of,
            )
            raise DatabaseException("Failed to get current shift assignment") from exc

    async def get_open_overnight_record_for_checkout(
        self,
        employee_id: uuid.UUID,
        event_date: date,
    ) -> AttendanceRecord | None:
        try:
            previous_work_date = self.work_date_to_db_value(event_date - timedelta(days=1))
            stmt = (
                select(AttendanceRecord)
                .join(WorkShift, AttendanceRecord.shift_id == WorkShift.shift_id)
                .options(selectinload(AttendanceRecord.shift))
                .where(
                    AttendanceRecord.employee_id == employee_id,
                    AttendanceRecord.work_date == previous_work_date,
                    AttendanceRecord.check_in_time.is_not(None),
                    AttendanceRecord.check_out_time.is_(None),
                    WorkShift.is_overnight.is_(True),
                )
                .limit(1)
            )
            return await self.db.scalar(stmt)
        except Exception as exc:
            logger.exception(
                "Failed to get open overnight attendance record: employee_id=%s event_date=%s",
                employee_id,
                event_date,
            )
            raise DatabaseException("Failed to get open overnight attendance record") from exc

    async def list_record(
        self,
        query: schemas.AttendanceRecordListQuery,
    ) -> list[AttendanceRecord]:
        try:
            stmt: Select = select(AttendanceRecord).options(selectinload(AttendanceRecord.shift))

            if query.employee_id is not None:
                stmt = stmt.where(AttendanceRecord.employee_id == query.employee_id)
            if query.shift_id is not None:
                stmt = stmt.where(AttendanceRecord.shift_id == query.shift_id)
            if query.work_date_from is not None:
                stmt = stmt.where(
                    AttendanceRecord.work_date >= self.work_date_to_db_value(query.work_date_from)
                )
            if query.work_date_to is not None:
                stmt = stmt.where(
                    AttendanceRecord.work_date <= self.work_date_to_db_value(query.work_date_to)
                )
            if query.status is not None:
                stmt = stmt.where(AttendanceRecord.status == query.status)
            if query.source is not None:
                stmt = stmt.where(AttendanceRecord.source == query.source)

            stmt = stmt.order_by(
                AttendanceRecord.work_date.desc(),
                AttendanceRecord.created_at.desc(),
            )
            stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        except Exception as exc:
            logger.exception("Failed to list attendance records")
            raise DatabaseException("Failed to list attendance records") from exc

    async def summarize_records(
        self,
        query: schemas.AttendanceRecordSummaryQuery,
    ) -> dict[str, int]:
        try:
            stmt = select(AttendanceRecord.status, func.count()).group_by(AttendanceRecord.status)

            if query.employee_id is not None:
                stmt = stmt.where(AttendanceRecord.employee_id == query.employee_id)
            if query.shift_id is not None:
                stmt = stmt.where(AttendanceRecord.shift_id == query.shift_id)
            if query.work_date_from is not None:
                stmt = stmt.where(
                    AttendanceRecord.work_date >= self.work_date_to_db_value(query.work_date_from)
                )
            if query.work_date_to is not None:
                stmt = stmt.where(
                    AttendanceRecord.work_date <= self.work_date_to_db_value(query.work_date_to)
                )

            result = await self.db.execute(stmt)
            counts = {status: count for status, count in result.all()}
            present_days = counts.get(AttendanceRecordStatus.present, 0)
            late_days = counts.get(AttendanceRecordStatus.late, 0) + counts.get(
                AttendanceRecordStatus.late_and_early_leave,
                0,
            )
            absent_days = counts.get(AttendanceRecordStatus.absent, 0)

            return {
                "total_records": sum(counts.values()),
                "present_days": present_days,
                "late_days": late_days,
                "absent_days": absent_days,
            }
        except Exception as exc:
            logger.exception("Failed to summarize attendance records")
            raise DatabaseException("Failed to summarize attendance records") from exc

    async def update_record(
        self,
        record: AttendanceRecord,
        payload: schemas.AttendanceRecordUpdate,
    ) -> AttendanceRecord:
        update_data = payload.model_dump(exclude_unset=True)
        changed = False

        for field, value in update_data.items():
            if field == "work_date":
                value = self.work_date_to_db_value(value)
            if getattr(record, field) != value:
                setattr(record, field, value)
                changed = True

        if changed and "source" not in update_data:
            record.source = AttendanceSource.edited

        if changed:
            try:
                await self.db.commit()
                await self.db.refresh(record)
            except Exception as exc:
                await self.db.rollback()
                logger.exception(
                    "Failed to update attendance record: record_id=%s",
                    record.record_id,
                )
                raise DatabaseException("Failed to update attendance record") from exc

        updated = await self.get_record_by_id(record.record_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated attendance record")
        return updated

    def add_event(self, event: AttendanceEvent) -> None:
        try:
            self.db.add(event)
        except Exception as exc:
            logger.exception("Failed to add attendance event to session")
            raise DatabaseException("Failed to add attendance event") from exc

    def add_record(self, record: AttendanceRecord) -> None:
        try:
            self.db.add(record)
        except Exception as exc:
            logger.exception("Failed to add attendance record to session")
            raise DatabaseException("Failed to add attendance record") from exc

    async def flush(self) -> None:
        try:
            await self.db.flush()
        except Exception as exc:
            logger.exception("Failed to flush attendance transaction")
            raise DatabaseException("Failed to flush attendance transaction") from exc

    async def commit(self) -> None:
        try:
            await self.db.commit()
        except Exception as exc:
            logger.exception("Failed to commit attendance transaction")
            raise DatabaseException("Failed to commit attendance transaction") from exc

    async def rollback(self) -> None:
        try:
            await self.db.rollback()
        except Exception as exc:
            logger.exception("Failed to rollback attendance transaction")
            raise DatabaseException("Failed to rollback attendance transaction") from exc

    async def refresh(self, obj) -> None:
        try:
            await self.db.refresh(obj)
        except Exception as exc:
            logger.exception("Failed to refresh attendance object")
            raise DatabaseException("Failed to refresh attendance object") from exc


def get_attendance_repo(db: AsyncSession = Depends(get_db)) -> AttendanceRepo:
    return AttendanceRepo(db)
