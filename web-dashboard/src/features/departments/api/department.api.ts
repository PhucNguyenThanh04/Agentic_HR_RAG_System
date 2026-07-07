import { api } from '@/lib/axios'
import type { CreateDepartmentPayload, Department } from '@/features/departments/types/department.types'

export const departmentApi = {
  listDepartments: async (search?: string): Promise<Department[]> => {
    const response = await api.get<Department[]>('/departments/', {
      params: { search: search || undefined },
    })
    return response.data
  },
  createDepartment: async (payload: CreateDepartmentPayload): Promise<Department> => {
    const response = await api.post<Department>('/departments/', payload)
    return response.data
  },
}
