import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useDeleteWorkShift() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: shiftApi.deleteWorkShift,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-shifts'] })
    },
  })
}
