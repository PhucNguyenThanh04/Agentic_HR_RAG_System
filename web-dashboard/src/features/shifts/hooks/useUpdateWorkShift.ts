import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useUpdateWorkShift() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: shiftApi.updateWorkShift,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-shifts'] })
    },
  })
}
