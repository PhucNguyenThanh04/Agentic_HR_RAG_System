import type { UUID } from '@/types/common.types'

export type AttendanceEventType = 'check_in' | 'check_out'

export type AttendanceEvent = {
  event_id: UUID
  employee_id: UUID | null
  event_type: AttendanceEventType
  event_time: string
  confidence_score: number | null
  anti_spoof_score: number | null
  image_url: string | null
  raw_result: Record<string, unknown> | null
  is_accepted: boolean
  rejection_reason: string | null
  created_at: string
}

export type AttendanceEventListParams = {
  page?: number
  page_size?: number
  employee_id?: string
  event_type?: AttendanceEventType
  accepted?: boolean
  event_time_from?: string
  event_time_to?: string
}
