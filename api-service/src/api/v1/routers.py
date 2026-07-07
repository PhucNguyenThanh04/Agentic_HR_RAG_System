from fastapi import APIRouter

from src.api.v1.features.attendance.controller import router as attendance_router
from src.api.v1.features.auth.controller import router as auth_router
from src.api.v1.features.chat.controller import router as conversations_router
from src.api.v1.features.documents.controller import router as documents_router
from src.api.v1.features.employee_onboarding.controller import (
    router as employee_onboarding_router,
)
from src.api.v1.features.face_profiles.controller import router as face_profile_router
from src.api.v1.features.leaves.controller import router as leaves_router
from src.api.v1.features.staff.departments.controller import router as department_router
from src.api.v1.features.staff.employees.controller import router as employee_router
from src.api.v1.features.users.controller import router as user_router
from src.api.v1.features.staff.position.controller import router as position_router
from src.api.v1.features.shifts.controller import (
    assignment_router,
    router as work_shift_router,
)
from src.api.v1.features.uploads_avartar.controller import router as upload_avatar_router

api_router = APIRouter()


api_router.include_router(auth_router)
api_router.include_router(user_router)
api_router.include_router(employee_router)
api_router.include_router(employee_onboarding_router)
api_router.include_router(department_router)
api_router.include_router(position_router)
api_router.include_router(work_shift_router)
api_router.include_router(assignment_router)
api_router.include_router(attendance_router)
api_router.include_router(leaves_router)
api_router.include_router(face_profile_router)
api_router.include_router(upload_avatar_router)
api_router.include_router(documents_router)
api_router.include_router(conversations_router)
