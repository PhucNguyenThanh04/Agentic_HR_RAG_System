import { useMutation } from '@tanstack/react-query'
import { onboardingApi } from '@/features/employee-onboarding/api/onboarding.api'

type UploadImagePayload = {
  file: File
  sessionId: string
}

export function useUploadOnboardingImage() {
  return useMutation({
    mutationFn: ({ file, sessionId }: UploadImagePayload) => onboardingApi.uploadImage(sessionId, file),
  })
}
