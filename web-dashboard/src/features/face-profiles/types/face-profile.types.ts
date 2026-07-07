import type { FaceProfileStatus, PaginatedResponse, UUID } from '@/types/common.types'

export type FaceProfile = {
  profile_id: UUID
  employee_id: UUID
  status: FaceProfileStatus
  qdrant_collection: string
  embedding_model: string | null
  embedding_version: string | null
  registered_by: UUID | null
  revocation_reason: string | null
  revoked_at: string | null
  created_at: string
  updated_at: string
}

export type FaceProfileListParams = {
  page?: number
  page_size?: number
  employee_id?: UUID
  status?: FaceProfileStatus
}

export type FaceProfileListResponse = PaginatedResponse<FaceProfile>
