import { useMutation, useQueryClient } from '@tanstack/react-query'
import { departmentApi } from '@/features/departments/api/department.api'

export function useCreateDepartment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: departmentApi.createDepartment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] })
    },
  })
}
