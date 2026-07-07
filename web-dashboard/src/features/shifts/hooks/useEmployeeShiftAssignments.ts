import { useQuery } from '@tanstack/react-query'
import { shiftApi } from '@/features/shifts/api/shift.api'

export function useEmployeeShiftAssignments(employeeId?: string, enabled = true) {
  return useQuery({
    enabled: enabled && Boolean(employeeId),
    queryFn: () => shiftApi.listEmployeeShiftAssignments(employeeId ?? ''),
    queryKey: ['shift-assignments', employeeId],
  })
}
