import { api } from '@/lib/axios'
import type {
  OnboardingCancelResponse,
  OnboardingCommitResponse,
  OnboardingPhotoUploadResponse,
  OnboardingStartPayload,
  OnboardingStartResponse,
} from '@/features/employee-onboarding/types/onboarding.types'

export const onboardingApi = {
  startSession: async (payload: OnboardingStartPayload): Promise<OnboardingStartResponse> => {
    const response = await api.post<OnboardingStartResponse>('/employee-onboarding/start-session', payload)
    return response.data
  },
  uploadImage: async (sessionId: string, file: File): Promise<OnboardingPhotoUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post<OnboardingPhotoUploadResponse>(
      `/employee-onboarding/${sessionId}/images`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      },
    )
    return response.data
  },
  commitSession: async (sessionId: string): Promise<OnboardingCommitResponse> => {
    const response = await api.post<OnboardingCommitResponse>('/employee-onboarding/commit', {
      session_id: sessionId,
    })
    return response.data
  },
  cancelSession: async (sessionId: string): Promise<OnboardingCancelResponse> => {
    const response = await api.delete<OnboardingCancelResponse>(`/employee-onboarding/${sessionId}`)
    return response.data
  },
}
