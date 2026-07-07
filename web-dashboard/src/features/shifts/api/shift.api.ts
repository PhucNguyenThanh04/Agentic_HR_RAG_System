import { api } from '@/lib/axios'
import type {
  CreateShiftAssignmentPayload,
  CreateWorkShiftPayload,
  ChangeShiftPayload,
  CurrentShift,
  EmployeeShiftAssignment,
  UpdateShiftAssignmentPayload,
  UpdateWorkShiftPayload,
  WorkShift,
  WorkShiftListParams,
} from '@/features/shifts/types/shift.types'

export const shiftApi = {
  listWorkShifts: async (params: WorkShiftListParams = {}): Promise<WorkShift[]> => {
    const response = await api.get<WorkShift[]>('/work-shifts/', { params })
    return response.data
  },
  createWorkShift: async (payload: CreateWorkShiftPayload): Promise<WorkShift> => {
    const response = await api.post<WorkShift>('/work-shifts/', payload)
    return response.data
  },
  updateWorkShift: async ({
    payload,
    shiftId,
  }: {
    payload: UpdateWorkShiftPayload
    shiftId: number
  }): Promise<WorkShift> => {
    const response = await api.patch<WorkShift>(`/work-shifts/${shiftId}`, payload)
    return response.data
  },
  deleteWorkShift: async (shiftId: number): Promise<void> => {
    await api.delete(`/work-shifts/${shiftId}`)
  },
  activateWorkShift: async (shiftId: number): Promise<WorkShift> => {
    const response = await api.patch<WorkShift>(`/work-shifts/${shiftId}/activate`)
    return response.data
  },
  deactivateWorkShift: async (shiftId: number): Promise<WorkShift> => {
    const response = await api.patch<WorkShift>(`/work-shifts/${shiftId}/deactivate`)
    return response.data
  },
  listEmployeeShiftAssignments: async (employeeId: string): Promise<EmployeeShiftAssignment[]> => {
    const response = await api.get<EmployeeShiftAssignment[]>(
      `/employees/${employeeId}/shift-assignments`,
    )
    return response.data
  },
  getEmployeeCurrentShift: async ({
    asOf,
    employeeId,
  }: {
    asOf?: string
    employeeId: string
  }): Promise<CurrentShift> => {
    const response = await api.get<CurrentShift>(`/employees/${employeeId}/current-shift`, {
      params: { as_of: asOf || undefined },
    })
    return response.data
  },
  createEmployeeShiftAssignment: async ({
    employeeId,
    payload,
  }: {
    employeeId: string
    payload: CreateShiftAssignmentPayload
  }): Promise<EmployeeShiftAssignment> => {
    const response = await api.post<EmployeeShiftAssignment>(
      `/employees/${employeeId}/shift-assignments`,
      payload,
    )
    return response.data
  },
  updateShiftAssignment: async ({
    assignmentId,
    payload,
  }: {
    assignmentId: number
    payload: UpdateShiftAssignmentPayload
  }): Promise<EmployeeShiftAssignment> => {
    const response = await api.patch<EmployeeShiftAssignment>(
      `/shift-assignments/${assignmentId}`,
      payload,
    )
    return response.data
  },
  deleteShiftAssignment: async (assignmentId: number): Promise<void> => {
    await api.delete(`/shift-assignments/${assignmentId}`)
  },
  closeShiftAssignment: async (assignmentId: number): Promise<EmployeeShiftAssignment> => {
    const response = await api.patch<EmployeeShiftAssignment>(
      `/shift-assignments/${assignmentId}/close`,
    )
    return response.data
  },
  changeEmployeeShift: async ({
    employeeId,
    payload,
  }: {
    employeeId: string
    payload: ChangeShiftPayload
  }): Promise<EmployeeShiftAssignment> => {
    const response = await api.post<EmployeeShiftAssignment>(
      `/employees/${employeeId}/change-shift`,
      payload,
    )
    return response.data
  },
}
