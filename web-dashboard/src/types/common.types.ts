export type UUID = string

export type RoleName = 'admin' | 'hr' | 'manager' | 'employee'

export type UserStatus = 'active' | 'inactive' | 'locked'

export type EmployeeStatus = 'active' | 'inactive' | 'resigned'

export type FaceProfileStatus = 'pending' | 'active' | 'revoked' | 'failed'

export type PaginatedResponse<TItem> = {
  items: TItem[]
  total: number
  page: number
  page_size: number
}

export type MessageResponse = {
  message: string
}

export type ApiQueryParams = Record<string, string | number | boolean | null | undefined>
