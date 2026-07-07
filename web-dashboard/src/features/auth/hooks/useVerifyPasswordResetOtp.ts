import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/features/auth/api/auth.api'

export function useVerifyPasswordResetOtp() {
  return useMutation({
    mutationFn: authApi.verifyPasswordResetOtp,
  })
}
