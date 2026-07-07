from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Depends
from redis.asyncio import Redis

from src.api.v1.features.attendance import schemas
from src.api.v1.features.attendance.models import AttendanceEvent, AttendanceRecord
from src.api.v1.features.attendance.repo import AttendanceRepo, get_attendance_repo
from src.api.v1.shared.enums import (
    AttendanceEventType,
    AttendanceRecordStatus,
    AttendanceSource,
    EmployeeStatus,
)
from src.core.configs.settings import settings
from src.core.dependencies.dep import get_redis_client
from src.utils.exeptions import (
    AppException,
    DatabaseException,
    NotFoundException,
    ValidationException,
)
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)
APP_TZ = ZoneInfo(settings.database_timezone)

COOLDOWN_SECONDS = 600
REASON_DUPLICATE_ATTENDANCE = "DUPLICATE_ATTENDANCE"
REASON_ATTENDANCE_ALREADY_COMPLETED = "ATTENDANCE_ALREADY_COMPLETED"
REASON_EMPLOYEE_INACTIVE = "EMPLOYEE_INACTIVE"
REASON_NO_ACTIVE_SHIFT_ASSIGNMENT = "NO_ACTIVE_SHIFT_ASSIGNMENT"


class AttendanceService:
    def __init__(self, attendance_repo: AttendanceRepo, redis_client: Redis | None):
        self.attendance_repo = attendance_repo
        self.redis = redis_client

    @staticmethod
    def _cooldown_key(employee_id: uuid.UUID) -> str:
        return f"attendance:cooldown:{employee_id}"

    @staticmethod
    def _normalize_event_time(event_time: datetime | None) -> datetime:
        if event_time is None:
            return datetime.now(timezone.utc)
        if event_time.tzinfo is None:
            return event_time.replace(tzinfo=timezone.utc)
        return event_time

    @staticmethod
    def _to_app_timezone(event_time: datetime) -> datetime:
        return event_time.astimezone(APP_TZ)

    @staticmethod
    def _combine_shift_datetime(
        work_date: date,
        shift_time: time,
        event_time: datetime,
    ) -> datetime:
        value = datetime.combine(work_date, shift_time)
        if event_time.tzinfo is not None and value.tzinfo is None:
            value = value.replace(tzinfo=event_time.tzinfo)
        return value

    @classmethod
    def _shift_start_datetime(cls, shift, work_date: date, event_time: datetime) -> datetime:
        return cls._combine_shift_datetime(work_date, shift.start_time, event_time)

    @classmethod
    def _shift_end_datetime(cls, shift, work_date: date, event_time: datetime) -> datetime:
        value = cls._combine_shift_datetime(work_date, shift.end_time, event_time)
        if shift.is_overnight:
            value += timedelta(days=1)
        return value

    @classmethod
    def _late_minutes(cls, shift, work_date: date, event_time: datetime) -> int:
        scheduled_start = cls._shift_start_datetime(shift, work_date, event_time)
        grace_until = scheduled_start + timedelta(minutes=shift.late_threshold_minutes or 0)
        if event_time <= grace_until:
            return 0
        return max(0, int((event_time - scheduled_start).total_seconds() // 60))

    @classmethod
    def _early_leave_minutes(cls, shift, work_date: date, event_time: datetime) -> int:
        scheduled_end = cls._shift_end_datetime(shift, work_date, event_time)
        allowed_from = scheduled_end - timedelta(minutes=shift.early_leave_threshold_minutes or 0)
        if event_time >= allowed_from:
            return 0
        return max(0, int((scheduled_end - event_time).total_seconds() // 60))

    @staticmethod
    def _worked_minutes(check_in_time: datetime, check_out_time: datetime) -> int:
        seconds = (check_out_time - check_in_time).total_seconds()
        return max(0, int(seconds // 60))

    @staticmethod
    def _status_for_check_out(late_minutes: int, early_leave_minutes: int) -> AttendanceRecordStatus:
        if late_minutes > 0 and early_leave_minutes > 0:
            return AttendanceRecordStatus.late_and_early_leave
        if early_leave_minutes > 0:
            return AttendanceRecordStatus.early_leave
        if late_minutes > 0:
            return AttendanceRecordStatus.late
        return AttendanceRecordStatus.present

    @staticmethod
    def _rejected_response(
        *,
        employee_id: uuid.UUID,
        event_time: datetime,
        reason: str,
        cooldown_ttl_seconds: int | None = None,
    ) -> schemas.AttendanceEventAcceptedResponse:
        return schemas.AttendanceEventAcceptedResponse(
            accepted=False,
            reason=reason,
            employee_id=employee_id,
            event_time=event_time,
            cooldown_ttl_seconds=cooldown_ttl_seconds,
        )

    async def create_event_from_ai(
        self,
        payload: schemas.AttendanceAIEventCreate,
    ) -> schemas.AttendanceEventAcceptedResponse:
        event_time = self._normalize_event_time(payload.event_time)
        attendance_time = self._to_app_timezone(event_time)
        employee_id = payload.employee_id
        if self.redis is None:
            raise RuntimeError("Redis client is required to create attendance events")

        employee_status = await self.attendance_repo.get_employee_status(employee_id)
        if employee_status is None:
            logger.warning("Attendance event employee not found: employee_id=%s", employee_id)
            raise NotFoundException("Employee")
        if employee_status != EmployeeStatus.active:
            logger.info(
                "Attendance rejected because employee is not active: employee_id=%s status=%s",
                employee_id,
                employee_status,
            )
            return self._rejected_response(
                employee_id=employee_id,
                event_time=event_time,
                reason=REASON_EMPLOYEE_INACTIVE,
            )

        cooldown_key = self._cooldown_key(employee_id)
        cooldown_value = await self.redis.get(cooldown_key)
        if cooldown_value is not None:
            ttl = await self.redis.ttl(cooldown_key)
            logger.info(
                "Attendance rejected by cooldown: employee_id=%s ttl=%s",
                employee_id,
                ttl,
            )
            return self._rejected_response(
                employee_id=employee_id,
                event_time=event_time,
                reason=REASON_DUPLICATE_ATTENDANCE,
                cooldown_ttl_seconds=ttl if ttl and ttl > 0 else None,
            )

        event_date = attendance_time.date()
        record = await self.attendance_repo.get_open_overnight_record_for_checkout(
            employee_id=employee_id,
            event_date=event_date,
        )
        if record is not None:
            work_date = record.work_date.date()
            shift = record.shift
        else:
            work_date = event_date
            record = await self.attendance_repo.get_record_by_employee_and_work_date(
                employee_id=employee_id,
                work_date=work_date,
            )
            shift = record.shift if record is not None else None

        if shift is None:
            assignment = await self.attendance_repo.get_current_shift_assignment(
                employee_id=employee_id,
                as_of=work_date,
            )
            if assignment is None or assignment.shift is None:
                logger.info(
                    "Attendance rejected because employee has no active shift assignment: employee_id=%s work_date=%s",
                    employee_id,
                    work_date,
                )
                return self._rejected_response(
                    employee_id=employee_id,
                    event_time=event_time,
                    reason=REASON_NO_ACTIVE_SHIFT_ASSIGNMENT,
                )
            shift = assignment.shift

        if record is None or record.check_in_time is None:
            event_type = AttendanceEventType.check_in
        elif record.check_out_time is None:
            event_type = AttendanceEventType.check_out
        else:
            logger.info(
                "Attendance already completed: employee_id=%s work_date=%s record_id=%s",
                employee_id,
                work_date,
                record.record_id,
            )
            return self._rejected_response(
                employee_id=employee_id,
                event_time=event_time,
                reason=REASON_ATTENDANCE_ALREADY_COMPLETED,
            )

        event = AttendanceEvent(
            employee_id=employee_id,
            event_type=event_type,
            event_time=event_time,
            confidence_score=payload.confidence_score,
            anti_spoof_score=payload.anti_spoof_score,
            image_url=payload.image_url,
            raw_result=payload.raw_result,
            is_accepted=True,
            rejection_reason=None,
        )
        self.attendance_repo.add_event(event)

        if event_type == AttendanceEventType.check_in:
            if record is None:
                record = AttendanceRecord(
                    employee_id=employee_id,
                    shift_id=shift.shift_id,
                    work_date=self.attendance_repo.work_date_to_db_value(work_date),
                    status=AttendanceRecordStatus.present,
                    late_minutes=0,
                    early_leave_minutes=0,
                    worked_minutes=0,
                    source=AttendanceSource.face_recognition,
                )
                self.attendance_repo.add_record(record)
            elif record.shift_id is None:
                record.shift_id = shift.shift_id

            late_minutes = self._late_minutes(shift, work_date, attendance_time)
            record.check_in_time = event_time
            record.source = AttendanceSource.face_recognition
            record.late_minutes = late_minutes
            record.early_leave_minutes = record.early_leave_minutes or 0
            record.worked_minutes = 0
            record.status = (
                AttendanceRecordStatus.late
                if late_minutes > 0
                else AttendanceRecordStatus.present
            )
        else:
            if record is None or record.check_in_time is None:
                raise DatabaseException("Attendance record is missing check-in state")
            if record.shift_id is None:
                record.shift_id = shift.shift_id

            early_leave_minutes = self._early_leave_minutes(shift, work_date, attendance_time)
            record.check_out_time = event_time
            record.source = AttendanceSource.face_recognition
            record.early_leave_minutes = early_leave_minutes
            record.worked_minutes = self._worked_minutes(record.check_in_time, event_time)
            record.status = self._status_for_check_out(
                late_minutes=record.late_minutes or 0,
                early_leave_minutes=early_leave_minutes,
            )

        try:
            await self.attendance_repo.flush()
            await self.attendance_repo.commit()
            await self.attendance_repo.refresh(event)
            await self.attendance_repo.refresh(record)
        except Exception as exc:
            try:
                await self.attendance_repo.rollback()
            except Exception:
                logger.exception(
                    "Failed to rollback attendance transaction after create event failure: employee_id=%s event_type=%s",
                    employee_id,
                    event_type,
                )
            logger.exception(
                "Failed to create attendance event: employee_id=%s event_type=%s",
                employee_id,
                event_type,
            )
            if isinstance(exc, DatabaseException):
                raise
            raise DatabaseException("Failed to create attendance event") from exc

        await self.redis.set(
            cooldown_key,
            str(event.event_id or event_time.isoformat()),
            ex=COOLDOWN_SECONDS,
        )
        logger.info(
            "Attendance accepted: employee_id=%s event_id=%s record_id=%s event_type=%s",
            employee_id,
            event.event_id,
            record.record_id,
            event_type,
        )

        return schemas.AttendanceEventAcceptedResponse(
            accepted=True,
            reason=None,
            employee_id=employee_id,
            event_id=event.event_id,
            record_id=record.record_id,
            shift_id=record.shift_id,
            event_type=event_type,
            event_time=event_time,
            work_date=work_date,
            check_in_time=record.check_in_time,
            check_out_time=record.check_out_time,
            late_minutes=record.late_minutes,
            early_leave_minutes=record.early_leave_minutes,
            worked_minutes=record.worked_minutes,
            status=record.status,
            cooldown_ttl_seconds=COOLDOWN_SECONDS,
        )

    async def list_events(
        self,
        query: schemas.AttendanceEventListQuery,
    ) -> list[schemas.AttendanceEventRead]:
        try:
            events = await self.attendance_repo.list_events(query)
            return [schemas.AttendanceEventRead.model_validate(event) for event in events]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to list attendance events")
            raise DatabaseException("Failed to list attendance events") from exc

    async def get_event(self, event_id: uuid.UUID) -> schemas.AttendanceEventRead:
        try:
            event = await self.attendance_repo.get_event_by_id(event_id)
            if event is None:
                logger.warning("Attendance event not found: event_id=%s", event_id)
                raise NotFoundException("Attendance event")
            return schemas.AttendanceEventRead.model_validate(event)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to get attendance event: event_id=%s", event_id)
            raise DatabaseException("Failed to get attendance event") from exc

    async def list_record(
        self,
        query: schemas.AttendanceRecordListQuery,
    ) -> list[schemas.AttendanceRecordRead]:
        try:
            records = await self.attendance_repo.list_record(query)
            return [schemas.AttendanceRecordRead.model_validate(record) for record in records]
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to list attendance records")
            raise DatabaseException("Failed to list attendance records") from exc

    async def get_record(self, record_id: uuid.UUID) -> schemas.AttendanceRecordRead:
        try:
            record = await self.attendance_repo.get_record_by_id(record_id)
            if record is None:
                logger.warning("Attendance record not found: record_id=%s", record_id)
                raise NotFoundException("Attendance record")
            return schemas.AttendanceRecordRead.model_validate(record)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to get attendance record: record_id=%s", record_id)
            raise DatabaseException("Failed to get attendance record") from exc

    async def summarize_records(
        self,
        query: schemas.AttendanceRecordSummaryQuery,
    ) -> schemas.AttendanceRecordSummaryRead:
        try:
            summary = await self.attendance_repo.summarize_records(query)
            return schemas.AttendanceRecordSummaryRead(**summary)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to summarize attendance records")
            raise DatabaseException("Failed to summarize attendance records") from exc

    @staticmethod
    def _validate_record_update(
        record: AttendanceRecord,
        payload: schemas.AttendanceRecordUpdate,
    ) -> None:
        required_fields = {
            "work_date",
            "status",
            "late_minutes",
            "early_leave_minutes",
            "worked_minutes",
            "source",
        }
        null_required_fields = [
            field
            for field in required_fields
            if field in payload.model_fields_set and getattr(payload, field) is None
        ]
        if null_required_fields:
            raise ValidationException(
                f"{', '.join(sorted(null_required_fields))} cannot be null"
            )

        check_in_time = (
            payload.check_in_time
            if "check_in_time" in payload.model_fields_set
            else record.check_in_time
        )
        check_out_time = (
            payload.check_out_time
            if "check_out_time" in payload.model_fields_set
            else record.check_out_time
        )
        if check_in_time and check_out_time and check_out_time < check_in_time:
            raise ValidationException("check_out_time must be on/after check_in_time")

    async def update_record(
        self,
        record_id: uuid.UUID,
        payload: schemas.AttendanceRecordUpdate,
    ) -> schemas.AttendanceRecordRead:
        try:
            record = await self.attendance_repo.get_record_by_id(record_id)
            if record is None:
                logger.warning("Attendance record not found for update: record_id=%s", record_id)
                raise NotFoundException("Attendance record")

            self._validate_record_update(record, payload)
            updated = await self.attendance_repo.update_record(record, payload)
            logger.info("Attendance record updated: record_id=%s", record_id)
            return schemas.AttendanceRecordRead.model_validate(updated)
        except AppException:
            raise
        except Exception as exc:
            logger.exception("Failed to update attendance record: record_id=%s", record_id)
            raise DatabaseException("Failed to update attendance record") from exc


def get_attendance_service(
    attendance_repo: AttendanceRepo = Depends(get_attendance_repo),
    redis_client: Redis = Depends(get_redis_client),
) -> AttendanceService:
    return AttendanceService(attendance_repo=attendance_repo, redis_client=redis_client)


def get_attendance_read_service(
    attendance_repo: AttendanceRepo = Depends(get_attendance_repo),
) -> AttendanceService:
    return AttendanceService(attendance_repo=attendance_repo, redis_client=None)
