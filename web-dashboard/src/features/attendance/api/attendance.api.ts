import { api } from '@/lib/axios'
import type {
  AttendanceEvent,
  AttendanceEventListParams,
} from '@/features/attendance/types/attendance.types'

export const attendanceApi = {
  listEvents: async (params: AttendanceEventListParams): Promise<AttendanceEvent[]> => {
    const response = await api.get<AttendanceEvent[]>('/attendance/events', { params })
    return response.data
  },
  getEventById: async (eventId: string): Promise<AttendanceEvent> => {
    const response = await api.get<AttendanceEvent>(`/attendance/events/${eventId}`)
    return response.data
  },
}
