import type { UUID } from '@/types/common.types'

export type WorkShift = {
  shift_id: number
  name: string
  code: string | null
  start_time: string
  end_time: string
  is_overnight: boolean
  late_threshold_minutes: number
  early_leave_threshold_minutes: number
  required_work_minutes: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type WorkShiftListParams = {
  search?: string
  is_active?: boolean
  code?: string
}

export type CreateWorkShiftPayload = {
  name: string
  code: string | null
  start_time: string
  end_time: string
  is_overnight: boolean
  late_threshold_minutes: number
  early_leave_threshold_minutes: number
  required_work_minutes: number | null
  is_active: boolean
}

export type UpdateWorkShiftPayload = Partial<CreateWorkShiftPayload>

export type EmployeeShiftAssignment = {
  assignment_id: number
  employee_id: UUID
  shift_id: number
  effective_date: string
  end_date: string | null
  created_by: UUID | null
  created_at: string
  updated_at: string
}

export type CreateShiftAssignmentPayload = {
  shift_id: number
  effective_date: string
  end_date: string | null
}

export type UpdateShiftAssignmentPayload = Partial<CreateShiftAssignmentPayload>

export type CurrentShift = {
  assignment_id: number
  employee_id: UUID
  effective_date: string
  end_date: string | null
  shift: WorkShift
}

export type ChangeShiftPayload = {
  new_shift_id: number
  effective_date: string
  reason: string | null
}
