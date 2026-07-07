import { useQuery } from '@tanstack/react-query'
import { attendanceApi } from '@/features/attendance/api/attendance.api'
import type { AttendanceEventListParams } from '@/features/attendance/types/attendance.types'

export function useAttendanceEvents(params: AttendanceEventListParams, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => attendanceApi.listEvents(params),
    queryKey: ['attendance', 'events', params],
  })
}
