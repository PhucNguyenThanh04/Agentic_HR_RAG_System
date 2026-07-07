import type { UUID } from '@/types/common.types'

export type OnboardingSessionStatus =
  | 'pending'
  | 'ready_to_commit'
  | 'committed'
  | 'cancelled'
  | 'failed'
  | 'expired'

export type OnboardingStartPayload = {
  email: string
  password: string
  full_name: string
  department_id: number
  position_id: number
}

export type OnboardingStartResponse = {
  session_id: string
  status: OnboardingSessionStatus
  expires_at: string
  min_required_photos: number
  current_valid_photos: number
}

export type OnboardingPhotoUploadResponse = {
  session_id: string
  accepted: boolean
  reason: string | null
  quality_score: number | null
  valid_photo_count: number
  min_required_photos: number
  ready_to_commit: boolean
}

export type OnboardingCommitResponse = {
  session_id: string
  status: OnboardingSessionStatus
  user_id: UUID
  employee_id: UUID
  employee_code: string
  face_profile_id: UUID | null
  vectors_stored: number | null
}

export type OnboardingCancelResponse = {
  session_id: string
  cancelled: boolean
  status: OnboardingSessionStatus
}
