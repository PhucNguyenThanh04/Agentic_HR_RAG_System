import { api } from '@/lib/axios'
import type {
  Employee,
  EmployeeListParams,
  EmployeeListResponse,
} from '@/features/employees/types/employee.types'

export const employeeApi = {
  listEmployees: async (params: EmployeeListParams): Promise<EmployeeListResponse> => {
    const response = await api.get<EmployeeListResponse>('/employees/', { params })
    return response.data
  },
  getEmployeeById: async (employeeId: string): Promise<Employee> => {
    const response = await api.get<Employee>(`/employees/${employeeId}`)
    return response.data
  },
  getMyEmployeeProfile: async (): Promise<Employee> => {
    const response = await api.get<Employee>('/employees/me')
    return response.data
  },
}
