import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { leaveApi } from '../api/leave.api'
import type {
  LeaveRequestListParams,
  ReviewLeaveRequestPayload,
  LeaveTypeUpdatePayload,
} from '../types/leave.types'

export function useLeaveRequests(params: LeaveRequestListParams, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => leaveApi.listLeaveRequests(params),
    queryKey: ['leave-requests', params],
  })
}

export function useLeaveTypes() {
  return useQuery({
    queryFn: () => leaveApi.listLeaveTypes(),
    queryKey: ['leave-types'],
  })
}

export function useLeaveBalance(employeeId?: string, year?: number) {
  return useQuery({
    enabled: Boolean(employeeId),
    queryFn: () => leaveApi.getLeaveBalance(employeeId!, year),
    queryKey: ['leave-balance', employeeId, year],
  })
}

export function useLeaveRequestLogs(requestId?: string) {
  return useQuery({
    enabled: Boolean(requestId),
    queryFn: () => leaveApi.listLeaveRequestLogs(requestId!),
    queryKey: ['leave-request-logs', requestId],
  })
}

export function useCreateLeaveRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: leaveApi.createLeaveRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leave-requests'] })
      queryClient.invalidateQueries({ queryKey: ['leave-balance'] })
    },
  })
}

export function useCancelLeaveRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: leaveApi.cancelLeaveRequest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leave-requests'] })
      queryClient.invalidateQueries({ queryKey: ['leave-balance'] })
    },
  })
}

export function useReviewLeaveRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ requestId, payload }: { requestId: string; payload: ReviewLeaveRequestPayload }) =>
      leaveApi.reviewLeaveRequest(requestId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leave-requests'] })
      queryClient.invalidateQueries({ queryKey: ['leave-balance'] })
    },
  })
}

export function useCreateLeaveType() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: leaveApi.createLeaveType,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leave-types'] })
    },
  })
}

export function useUpdateLeaveType() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: LeaveTypeUpdatePayload }) =>
      leaveApi.updateLeaveType(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leave-types'] })
    },
  })
}
