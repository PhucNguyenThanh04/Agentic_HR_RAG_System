from __future__ import annotations

import uuid

import httpx
from fastapi import Depends

from src.api.v1.features.staff.employees import schemas
from src.api.v1.features.staff.employees.employee_repo import EmployeeRepo, get_employee_repo
from src.api.v1.shared.enums import EmployeeStatus, FaceProfileStatus, UserStatus
from src.core.clients.face_server.clients import FaceServerClient
from src.core.dependencies.dep import get_ai_http_client
from src.utils.exeptions import (
    BadRequestException,
    ConflictException,
    MLProcessingException,
    NotFoundException,
)
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class EmployeeService:
    def __init__(self, employee_repo: EmployeeRepo, face_server_client: FaceServerClient):
        self.employee_repo = employee_repo
        self.face_server_client = face_server_client

    @staticmethod
    def _to_read(employee) -> schemas.EmployeeRead:
        return schemas.EmployeeRead.model_validate(employee)

    async def employee_code_exists(self, employee_code: str) -> bool:
        return await self.employee_repo.employee_code_exists(employee_code)

    async def department_exists_active(self, department_id: int) -> None:
        dep = await self.employee_repo.department_exists(department_id)
        if dep is None:
            raise BadRequestException("Department not found")
        if not dep.is_active:
            raise BadRequestException("Department is inactive")

    async def position_exists_active(self, position_id: int) -> None:
        pos = await self.employee_repo.position_exists(position_id)
        if pos is None:
            raise BadRequestException("Position not found")
        if not pos.is_active:
            raise BadRequestException("Position is inactive")


    async def _validate_references_on_create(self, payload: schemas.EmployeeCreate) -> None:
        if payload.user_id is not None:
            if not await self.employee_repo.user_exists(payload.user_id):
                raise BadRequestException("User not found")
            if await self.employee_repo.user_linked_to_other_employee(payload.user_id):
                raise ConflictException("User is already linked to another employee")
        if payload.employee_code is not None and await self.employee_repo.employee_code_exists(
            payload.employee_code
        ):
            raise ConflictException("Employee code already exists")

        if payload.department_id is not None and not await self.employee_repo.department_exists(
            payload.department_id
        ):
            raise BadRequestException("Department not found")

        if payload.position_id is not None and not await self.employee_repo.position_exists(
            payload.position_id
        ):
            raise BadRequestException("Position not found")

        if payload.manager_id is not None and not await self.employee_repo.manager_exists(
            payload.manager_id
        ):
            raise BadRequestException("Manager not found")

    async def _validate_references_on_update(
        self,
        employee_id: uuid.UUID,
        existing,
        payload: schemas.EmployeeUpdate,
    ) -> None:
        if payload.user_id is not None:
            if not await self.employee_repo.user_exists(payload.user_id):
                raise BadRequestException("User not found")
            if await self.employee_repo.user_linked_to_other_employee(
                payload.user_id,
                exclude_employee_id=employee_id,
            ):
                raise ConflictException("User is already linked to another employee")

        if payload.department_id is not None and not await self.employee_repo.department_exists(
            payload.department_id
        ):
            raise BadRequestException("Department not found")

        if payload.position_id is not None and not await self.employee_repo.position_exists(
            payload.position_id
        ):
            raise BadRequestException("Position not found")

        if payload.manager_id is not None:
            if payload.manager_id == employee_id:
                raise BadRequestException("Employee cannot be their own manager")
            if not await self.employee_repo.manager_exists(payload.manager_id):
                raise BadRequestException("Manager not found")

    async def _deactivate_ai_vectors_for_employee(
        self,
        *,
        employee_id: uuid.UUID,
        reason: str,
    ) -> None:
        try:
            result = await self.face_server_client.deactivate_person(str(employee_id))
            logger.info(
                "AI vectors deactivated for employee: employee_id=%s vectors_updated=%s reason=%s",
                employee_id,
                result.vectors_updated,
                reason,
            )
        except httpx.HTTPError as exc:
            logger.exception(
                "Failed to deactivate AI vectors for employee: employee_id=%s reason=%s",
                employee_id,
                reason,
            )
            raise MLProcessingException(
                step="deactivate_employee_vectors",
                reason=str(exc),
                task_id=str(employee_id),
            ) from exc

    async def _deactivate_ai_vectors_if_profile_exists(
        self,
        *,
        employee_id: uuid.UUID,
        reason: str,
    ) -> None:
        profile = await self.employee_repo.get_face_profile_by_employee_id(employee_id)
        if profile is None:
            logger.info(
                "Skip AI vector cleanup because employee has no face profile: employee_id=%s reason=%s",
                employee_id,
                reason,
            )
            return

        await self._deactivate_ai_vectors_for_employee(employee_id=employee_id, reason=reason)

    async def _activate_ai_vectors_for_employee(
        self,
        *,
        employee_id: uuid.UUID,
        reason: str,
    ) -> None:
        try:
            result = await self.face_server_client.activate_person(str(employee_id))
            logger.info(
                "AI vectors activated for employee: employee_id=%s vectors_updated=%s reason=%s",
                employee_id,
                result.vectors_updated,
                reason,
            )
        except httpx.HTTPError as exc:
            logger.exception(
                "Failed to activate AI vectors for employee: employee_id=%s reason=%s",
                employee_id,
                reason,
            )
            raise MLProcessingException(
                step="activate_employee_vectors",
                reason=str(exc),
                task_id=str(employee_id),
            ) from exc

    async def _activate_ai_vectors_if_profile_exists(
        self,
        *,
        employee_id: uuid.UUID,
        reason: str,
    ) -> None:
        profile = await self.employee_repo.get_face_profile_by_employee_id(employee_id)
        if profile is None:
            logger.info(
                "Skip AI vector activation because employee has no face profile: employee_id=%s reason=%s",
                employee_id,
                reason,
            )
            return

        await self._activate_ai_vectors_for_employee(employee_id=employee_id, reason=reason)

    async def create_employee(
        self,
        payload: schemas.EmployeeCreate,
        registered_by: uuid.UUID | None = None,
    ) -> schemas.EmployeeRead:
        logger.info(
            "Create employee request: employee_code=%s user_id=%s full_name=%s registered_by=%s",
            payload.employee_code,
            payload.user_id,
            payload.full_name,
            registered_by,
        )

        if payload.employee_code:
            logger.info(
                "Create employee payload contains employee_code=%s but system will auto-generate",
                payload.employee_code,
            )

        await self._validate_references_on_create(payload)
        employee = await self.employee_repo.create_employee(
            payload=payload,
            registered_by=registered_by,
        )
        logger.info(
            "Employee created: employee_id=%s user_id=%s",
            employee.employee_id,
            employee.user_id,
        )
        return self._to_read(employee)

    async def get_employee(self, employee_id: uuid.UUID) -> schemas.EmployeeRead:
        employee = await self.employee_repo.get_employee_by_id(employee_id)
        if employee is None:
            logger.warning("Employee not found by id: employee_id=%s", employee_id)
            raise NotFoundException("Employee")
        return self._to_read(employee)

    async def get_employee_by_code(self, employee_code: str) -> schemas.EmployeeRead:
        employee = await self.employee_repo.get_employee_by_code(employee_code)
        if employee is None:
            logger.warning("Employee not found by code: employee_code=%s", employee_code)
            raise NotFoundException("Employee")
        return self._to_read(employee)

    async def list_employees(self, query: schemas.EmployeeListQuery) -> dict:
        employees, total = await self.employee_repo.list_employees(
            page=query.page,
            page_size=query.page_size,
            search=query.search,
            department_id=query.department_id,
            position_id=query.position_id,
            manager_id=query.manager_id,
            status=query.status,
        )
        logger.info(
            "List employees: page=%s page_size=%s total=%s search=%s",
            query.page,
            query.page_size,
            total,
            query.search,
        )
        return {
            "items": [self._to_read(employee) for employee in employees],
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }

    async def update_employee(
        self,
        employee_id: uuid.UUID,
        payload: schemas.EmployeeUpdate,
    ) -> schemas.EmployeeRead:
        existing = await self.employee_repo.get_employee_by_id(employee_id)
        if existing is None:
            logger.warning("Update employee not found: employee_id=%s", employee_id)
            raise NotFoundException("Employee")

        if (
            payload.employee_code is not None
            and await self.employee_repo.employee_code_exists(
                payload.employee_code,
                exclude_employee_id=employee_id,
            )
        ):
            logger.warning(
                "Update employee conflict code: employee_id=%s employee_code=%s",
                employee_id,
                payload.employee_code,
            )
            raise ConflictException("Employee code already exists")

        values = payload.model_dump(exclude_unset=True)
        if (
            "user_id" in values
            and existing.user_id is not None
            and payload.user_id != existing.user_id
        ):
            logger.warning(
                "Rejected employee user relink: employee_id=%s old_user_id=%s new_user_id=%s",
                employee_id,
                existing.user_id,
                payload.user_id,
            )
            raise BadRequestException(
                "Cannot change or unlink an existing employee user through employee update"
            )

        if (
            payload.employee_code is not None
            and existing.face_profile is not None
            and existing.face_profile.status == FaceProfileStatus.active
        ):
            raise BadRequestException(
                "Cannot change employee_code while face profile is active; revoke/re-enroll first"
            )

        await self._validate_references_on_update(employee_id, existing, payload)

        deactivate_links = payload.status in {
            EmployeeStatus.inactive,
            EmployeeStatus.resigned,
        }
        if deactivate_links:
            await self._deactivate_ai_vectors_if_profile_exists(
                employee_id=employee_id,
                reason=f"employee_status_changed_to_{payload.status.value}",
            )

        updated = await self.employee_repo.update_employee(
            employee_id,
            payload,
            deactivate_linked_entities=deactivate_links,
            deactivation_reason=(
                f"Employee status changed to {payload.status.value}"
                if deactivate_links and payload.status is not None
                else None
            ),
        )
        logger.info("Employee updated: employee_id=%s", employee_id)
        return self._to_read(updated)

    async def delete_employee(self, employee_id: uuid.UUID) -> None:
        employee = await self.employee_repo.get_employee_by_id(employee_id)
        if employee is None:
            logger.warning("Delete employee not found: employee_id=%s", employee_id)
            raise NotFoundException("Employee")

        await self._deactivate_ai_vectors_if_profile_exists(
            employee_id=employee_id,
            reason="employee_delete",
        )
        await self.employee_repo.soft_delete_employee_with_links(
            employee_id,
            reason="Employee deleted",
        )
        logger.info(
            "Employee soft deleted with linked user/profile cleanup: employee_id=%s user_id=%s",
            employee_id,
            employee.user_id,
        )

    async def hard_delete_employee_for_rollback(self, employee_id: uuid.UUID) -> None:
        await self.employee_repo.hard_delete_employee(employee_id)
        logger.warning("Employee hard deleted for rollback: employee_id=%s", employee_id)

    async def deactivate_employee(self, employee_id: uuid.UUID) -> schemas.EmployeeRead:
        employee = await self.employee_repo.get_employee_by_id(employee_id)
        if employee is None:
            logger.warning("Deactivate employee not found: employee_id=%s", employee_id)
            raise NotFoundException("Employee")

        already_clean = (
            employee.status == EmployeeStatus.inactive
            and (employee.user is None or employee.user.status == UserStatus.inactive)
            and (
                employee.face_profile is None
                or employee.face_profile.status == FaceProfileStatus.revoked
            )
        )
        if already_clean:
            logger.info("Employee already inactive: employee_id=%s", employee_id)
            return self._to_read(employee)

        await self._deactivate_ai_vectors_if_profile_exists(
            employee_id=employee_id,
            reason="employee_deactivate",
        )
        deactivated = await self.employee_repo.deactivate_employee(employee_id)
        logger.info("Employee deactivated with linked cleanup: employee_id=%s", employee_id)
        return self._to_read(deactivated)

    async def activate_employee(self, employee_id: uuid.UUID) -> schemas.EmployeeRead:
        employee = await self.employee_repo.get_employee_by_id(employee_id)
        if employee is None:
            logger.warning("Activate employee not found: employee_id=%s", employee_id)
            raise NotFoundException("Employee")

        already_active = (
            employee.status == EmployeeStatus.active
            and (employee.user is None or employee.user.status == UserStatus.active)
            and (
                employee.face_profile is None
                or employee.face_profile.status == FaceProfileStatus.active
            )
        )
        if already_active:
            logger.info("Employee already active: employee_id=%s", employee_id)
            return self._to_read(employee)

        await self._activate_ai_vectors_if_profile_exists(
            employee_id=employee_id,
            reason="employee_activate",
        )
        activated = await self.employee_repo.activate_employee_with_links(employee_id)
        logger.info("Employee activated with linked restore: employee_id=%s", employee_id)
        return self._to_read(activated)


def get_employee_service(
    employee_repo: EmployeeRepo = Depends(get_employee_repo),
    ai_http_client: httpx.AsyncClient = Depends(get_ai_http_client),
) -> EmployeeService:
    return EmployeeService(
        employee_repo=employee_repo,
        face_server_client=FaceServerClient(ai_http_client),
    )
