import { useMutation, useQueryClient } from '@tanstack/react-query'
import { onboardingApi } from '@/features/employee-onboarding/api/onboarding.api'

export function useCommitOnboardingSession() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: onboardingApi.commitSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] })
      queryClient.invalidateQueries({ queryKey: ['face-profiles'] })
    },
  })
}
