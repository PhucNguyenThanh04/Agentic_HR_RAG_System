export type Department = {
  department_id: number
  name: string
  code: string | null
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type CreateDepartmentPayload = {
  name: string
  code?: string | null
  description?: string | null
  is_active: boolean
}
