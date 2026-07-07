import type { UUID, PaginatedResponse } from '@/types/common.types'

export type LeaveRequestStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'

export type LeaveTimeType = 'full_day' | 'morning' | 'afternoon' | 'custom'

export type ApprovalAction = 'approved' | 'rejected' | 'forwarded' | 'cancelled'

export type LeaveType = {
  leave_type_id: number
  name: string
  code: string | null
  is_paid: boolean
  max_days_per_year: number | null
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type LeaveTypeCreatePayload = {
  name: string
  code?: string
  is_paid?: boolean
  max_days_per_year?: number
  description?: string
  is_active?: boolean
}

export type LeaveTypeUpdatePayload = Partial<LeaveTypeCreatePayload>

export type LeaveBalanceItem = {
  leave_type_id: number
  name: string
  code: string | null
  is_paid: boolean
  max_days_per_year: number | null
  used_days: number
  remaining_days: number | null
}

export type LeaveBalance = {
  employee_id: UUID
  year: number
  total_allowed_days: number
  total_used_days: number
  total_remaining_days: number
  items: LeaveBalanceItem[]
}

export type LeaveRequest = {
  request_id: UUID
  employee_id: UUID
  leave_type_id: number
  start_date: string
  end_date: string
  time_type: LeaveTimeType
  total_days: number | null
  reason: string | null
  status: LeaveRequestStatus
  approved_by: UUID | null
  approved_at: string | null
  rejection_reason: string | null
  created_at: string
  updated_at: string
}

export type LeaveRequestCreatePayload = {
  leave_type_id: number
  start_date: string
  end_date: string
  time_type?: LeaveTimeType
  total_days?: number
  reason?: string
}

export type LeaveRequestUpdatePayload = Partial<LeaveRequestCreatePayload> & {
  status?: LeaveRequestStatus
  approved_by?: UUID
  approved_at?: string
  rejection_reason?: string
}

export type LeaveApprovalLog = {
  log_id: number
  leave_request_id: UUID
  approver_id: UUID
  action: ApprovalAction
  comment: string | null
  created_at: string
}

export type ReviewLeaveRequestPayload = {
  action: ApprovalAction
  comment?: string
  rejection_reason?: string
}

export type LeaveRequestListParams = {
  page?: number
  page_size?: number
  employee_id?: UUID
  leave_type_id?: number
  status?: LeaveRequestStatus
  start_from?: string
  start_to?: string
}

export type LeaveRequestListResponse = PaginatedResponse<LeaveRequest>
