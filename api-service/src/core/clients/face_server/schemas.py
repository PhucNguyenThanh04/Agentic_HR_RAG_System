from __future__ import annotations

from pydantic import BaseModel, Field


EMBEDDING_VERSION = "insightface-buffalo_l-v1"

class AIServerPaths:
    HEALTH = "/health"
    FACES_BASE = "/api/v1/faces"
    ENROLL_PHOTO = "/api/v1/faces/enroll/photo"
    ENROLL_COMMIT = "/api/v1/faces/enroll/commit"
    ENROLL_REENROLL = "/api/v1/faces/enroll/re-enroll"

    @staticmethod
    def enroll_cancel(session_id: str) -> str:
        return f"{AIServerPaths.FACES_BASE}/enroll/{session_id}"

    @staticmethod
    def delete_person(staff_id: str) -> str:
        return f"{AIServerPaths.FACES_BASE}/{staff_id}"

    @staticmethod
    def deactivate_person(staff_id: str) -> str:
        return f"{AIServerPaths.FACES_BASE}/{staff_id}/deactivate"

    @staticmethod
    def activate_person(staff_id: str) -> str:
        return f"{AIServerPaths.FACES_BASE}/{staff_id}/activate"

    @staticmethod
    def enrolled_status(staff_id: str) -> str:
        return f"{AIServerPaths.FACES_BASE}/{staff_id}/status"


class AIPayloadCreateRequest(BaseModel):
    staff_id: str = Field(..., min_length=1, max_length=120)
    face_profile_id: str = Field(..., min_length=1, max_length=120)
    employee_code: str = Field(..., min_length=1, max_length=120)
    embedding_version: str = Field(default=EMBEDDING_VERSION, min_length=1, max_length=120)
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class AIEnrollPhotoParams(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=200)


class AIAddPhotoResponse(BaseModel):
    accepted: bool
    reason: str | None = None
    count: int | None = None
    quality_score: float | None = None


class AICommitRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=200)
    payload: AIPayloadCreateRequest


class AICommitResponse(BaseModel):
    success: bool
    staff_id: str
    face_profile_id: str
    vectors_stored: int


class AICancelEnrollmentResponse(BaseModel):
    cancelled: bool
    session_id: str


class AIDeletePersonResponse(BaseModel):
    deleted: bool
    staff_id: str
    vectors_removed: int


class AIDeactivatePersonResponse(BaseModel):
    deactivated: bool
    staff_id: str
    vectors_updated: int
    is_active: bool


class AIActivatePersonResponse(BaseModel):
    activated: bool
    staff_id: str
    vectors_updated: int
    is_active: bool


class AIEnrolledStatusResponse(BaseModel):
    enrolled: bool
    vector_count: int
    staff_id: str


class AIHealthResponse(BaseModel):
    status: str
    detail: str | None = None
