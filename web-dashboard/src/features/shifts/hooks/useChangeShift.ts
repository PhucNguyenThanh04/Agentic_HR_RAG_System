import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useChangeShift() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: shiftApi.changeEmployeeShift,
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['shift-assignments', variables.employeeId] })
      queryClient.invalidateQueries({ queryKey: ['current-shift', variables.employeeId] })
      queryClient.invalidateQueries({ queryKey: ['work-shifts'] })
    },
  })
}
