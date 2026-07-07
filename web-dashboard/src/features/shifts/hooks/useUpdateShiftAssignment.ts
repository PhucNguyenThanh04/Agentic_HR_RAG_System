import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useUpdateShiftAssignment(employeeId?: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: shiftApi.updateShiftAssignment,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shift-assignments', employeeId] })
      queryClient.invalidateQueries({ queryKey: ['current-shift', employeeId] })
    },
  })
}
