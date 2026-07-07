import { api } from '@/lib/axios'
import type {
  LeaveType,
  LeaveTypeCreatePayload,
  LeaveTypeUpdatePayload,
  LeaveBalance,
  LeaveRequest,
  LeaveRequestCreatePayload,
  LeaveRequestUpdatePayload,
  LeaveApprovalLog,
  ReviewLeaveRequestPayload,
  LeaveRequestListParams,
  LeaveRequestListResponse,
} from '../types/leave.types'

export const leaveApi = {
  // --- Leave Types ---
  listLeaveTypes: async (): Promise<LeaveType[]> => {
    const response = await api.get<LeaveType[]>('/leaves/types')
    return response.data
  },

  createLeaveType: async (payload: LeaveTypeCreatePayload): Promise<LeaveType> => {
    const response = await api.post<LeaveType>('/leaves/types', payload)
    return response.data
  },

  updateLeaveType: async (id: number, payload: LeaveTypeUpdatePayload): Promise<LeaveType> => {
    const response = await api.patch<LeaveType>(`/leaves/types/${id}`, payload)
    return response.data
  },

  // --- Leave Balances ---
  getLeaveBalance: async (employeeId: string, year?: number): Promise<LeaveBalance> => {
    const response = await api.get<LeaveBalance>(`/leaves/balance/${employeeId}`, {
      params: year ? { year } : undefined,
    })
    return response.data
  },

  // --- Leave Requests ---
  listLeaveRequests: async (params: LeaveRequestListParams): Promise<LeaveRequestListResponse> => {
    const response = await api.get<LeaveRequestListResponse>('/leaves/requests', { params })
    return response.data
  },

  createLeaveRequest: async (payload: LeaveRequestCreatePayload): Promise<LeaveRequest> => {
    const response = await api.post<LeaveRequest>('/leaves/requests', payload)
    return response.data
  },

  getLeaveRequest: async (requestId: string): Promise<LeaveRequest> => {
    const response = await api.get<LeaveRequest>(`/leaves/requests/${requestId}`)
    return response.data
  },

  updatePendingLeaveRequest: async (
    requestId: string,
    payload: LeaveRequestUpdatePayload
  ): Promise<LeaveRequest> => {
    const response = await api.patch<LeaveRequest>(`/leaves/requests/${requestId}`, payload)
    return response.data
  },

  cancelLeaveRequest: async (requestId: string): Promise<LeaveRequest> => {
    const response = await api.post<LeaveRequest>(`/leaves/requests/${requestId}/cancel`)
    return response.data
  },

  reviewLeaveRequest: async (
    requestId: string,
    payload: ReviewLeaveRequestPayload
  ): Promise<LeaveRequest> => {
    const response = await api.post<LeaveRequest>(`/leaves/requests/${requestId}/review`, payload)
    return response.data
  },

  listLeaveRequestLogs: async (requestId: string): Promise<LeaveApprovalLog[]> => {
    const response = await api.get<LeaveApprovalLog[]>(`/leaves/requests/${requestId}/logs`)
    return response.data
  },
}
