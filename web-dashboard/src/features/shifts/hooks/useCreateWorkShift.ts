import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useCreateWorkShift() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: shiftApi.createWorkShift,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-shifts'] })
    },
  })
}
