import type { EmployeeStatus, PaginatedResponse, UUID } from '@/types/common.types'

export type Employee = {
  employee_id: UUID
  user_id: UUID | null
  registered_by: UUID | null
  employee_code: string
  full_name: string
  phone: string | null
  avatar_url: string | null
  department_id: number | null
  position_id: number | null
  manager_id: UUID | null
  date_of_birth: string | null
  gender: string | null
  address: string | null
  hire_date: string | null
  resignation_date: string | null
  status: EmployeeStatus
  created_at: string
  updated_at: string
}

export type EmployeeListParams = {
  page?: number
  page_size?: number
  search?: string
  department_id?: number
  position_id?: number
  manager_id?: UUID
  status?: EmployeeStatus
}

export type EmployeeListResponse = PaginatedResponse<Employee>
