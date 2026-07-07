import { useMutation, useQueryClient } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useToggleWorkShift() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ isActive, shiftId }: { isActive: boolean; shiftId: number }) =>
      isActive ? shiftApi.deactivateWorkShift(shiftId) : shiftApi.activateWorkShift(shiftId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['work-shifts'] })
    },
  })
}
