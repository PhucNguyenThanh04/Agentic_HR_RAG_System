import { useQuery } from '@tanstack/react-query'
import { faceProfileApi } from '@/features/face-profiles/api/face-profile.api'
import type { FaceProfileListParams } from '@/features/face-profiles/types/face-profile.types'

export function useFaceProfiles(params: FaceProfileListParams, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => faceProfileApi.listFaceProfiles(params),
    queryKey: ['face-profiles', params],
  })
}
