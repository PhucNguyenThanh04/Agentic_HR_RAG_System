import type { PaginatedResponse, RoleName, UUID } from '@/types/common.types'

export type DocumentStatus = 'processing' | 'ready' | 'failed'

export type DocumentItem = {
  allowed_roles: RoleName[]
  chunk_count: number
  created_at: string
  file_name: string
  file_type: string
  file_url: string
  id: UUID
  qdrant_collection: string
  status: DocumentStatus
  title: string
  updated_at: string
  uploaded_by: UUID | null
}

export type DocumentListParams = {
  allowed_role?: RoleName | ''
  file_type?: string
  page: number
  page_size: number
  search?: string
  status?: DocumentStatus | ''
}

export type DocumentListResponse = PaginatedResponse<DocumentItem>

export type UploadDocumentPayload = {
  allowed_roles: RoleName[]
  file: File
  title: string
}
