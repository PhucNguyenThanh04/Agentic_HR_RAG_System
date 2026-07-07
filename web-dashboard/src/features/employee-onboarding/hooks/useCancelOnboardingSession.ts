import { useMutation } from '@tanstack/react-query'
import { onboardingApi } from '@/features/employee-onboarding/api/onboarding.api'

export function useCancelOnboardingSession() {
  return useMutation({
    mutationFn: onboardingApi.cancelSession,
  })
}
