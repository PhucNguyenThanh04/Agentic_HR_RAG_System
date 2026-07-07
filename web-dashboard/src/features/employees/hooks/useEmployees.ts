import { useQuery } from '@tanstack/react-query'
import { employeeApi } from '@/features/employees/api/employee.api'
import type { EmployeeListParams } from '@/features/employees/types/employee.types'

export function useEmployees(params: EmployeeListParams, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => employeeApi.listEmployees(params),
    queryKey: ['employees', params],
  })
}

export function useMyEmployeeProfile(enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => employeeApi.getMyEmployeeProfile(),
    queryKey: ['my-employee-profile'],
  })
}
