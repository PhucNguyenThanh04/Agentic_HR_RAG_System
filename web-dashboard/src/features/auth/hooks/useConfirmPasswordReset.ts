import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/features/auth/api/auth.api'

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: authApi.confirmPasswordReset,
  })
}
