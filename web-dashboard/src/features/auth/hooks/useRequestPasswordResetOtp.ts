import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/features/auth/api/auth.api'

export function useRequestPasswordResetOtp() {
  return useMutation({
    mutationFn: authApi.requestPasswordResetOtp,
  })
}
