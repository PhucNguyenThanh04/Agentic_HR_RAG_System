import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useCreateShiftAssignment() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: shiftApi.createEmployeeShiftAssignment,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['shift-assignments', variables.employeeId] })
      queryClient.invalidateQueries({ queryKey: ['current-shift', variables.employeeId] })
    },
  })
}
