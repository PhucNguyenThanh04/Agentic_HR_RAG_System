import { useMutation, useQueryClient } from '@tanstack/react-query'
import { faceProfileApi } from '@/features/face-profiles/api/face-profile.api'

export function useRevokeFaceProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ profileId, reason }: { profileId: string; reason: string }) =>
      faceProfileApi.revokeFaceProfile(profileId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['face-profiles'] })
    },
  })
}
