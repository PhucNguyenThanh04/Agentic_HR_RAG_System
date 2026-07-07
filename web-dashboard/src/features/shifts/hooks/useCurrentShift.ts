import { useQuery } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useCurrentShift(employeeId?: string, asOf?: string, enabled = true) {
  return useQuery({
    enabled: enabled && Boolean(employeeId),
    queryFn: () => shiftApi.getEmployeeCurrentShift({ asOf, employeeId: employeeId ?? '' }),
    queryKey: ['current-shift', employeeId, asOf],
    retry: false,
  })
}
