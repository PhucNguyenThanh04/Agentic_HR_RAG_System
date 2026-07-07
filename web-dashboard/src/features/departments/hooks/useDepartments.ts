import { useQuery } from '@tanstack/react-query'
import { departmentApi } from '@/features/departments/api/department.api'

export function useDepartments(search?: string, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => departmentApi.listDepartments(search),
    queryKey: ['departments', search],
  })
}
