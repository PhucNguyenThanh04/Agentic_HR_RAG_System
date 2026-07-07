import { api } from '@/lib/axios'
import type {
  FaceProfile,
  FaceProfileListParams,
  FaceProfileListResponse,
} from '@/features/face-profiles/types/face-profile.types'

export const faceProfileApi = {
  listFaceProfiles: async (params: FaceProfileListParams): Promise<FaceProfileListResponse> => {
    const response = await api.get<FaceProfileListResponse>('/face-profiles/', { params })
    return response.data
  },
  getFaceProfileByEmployee: async (employeeId: string): Promise<FaceProfile> => {
    const response = await api.get<FaceProfile>(`/face-profiles/employee/${employeeId}`)
    return response.data
  },
  revokeFaceProfile: async (profileId: string, reason: string): Promise<FaceProfile> => {
    const response = await api.post<FaceProfile>(`/face-profiles/${profileId}/revoke`, { reason })
    return response.data
  },
}

