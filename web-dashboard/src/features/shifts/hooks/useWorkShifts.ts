import { useQuery } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'
import type { WorkShiftListParams } from '@/features/shifts/types/shift.types'

export function useWorkShifts(params: WorkShiftListParams = {}, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => shiftApi.listWorkShifts(params),
    queryKey: ['work-shifts', params],
  })
}
