import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/features/auth/api/auth.api'
import type { LoginPayload, LoginResult } from '@/features/auth/types/auth.types'
import { tokenStorage } from '@/lib/storage'
import { useAuthStore } from '@/stores/auth.store'

export function useLogin() {
  const login = useAuthStore((state) => state.login)

  return useMutation({
    mutationFn: async (payload: LoginPayload): Promise<LoginResult> => {
      const tokens = await authApi.login(payload)
      tokenStorage.setAccessToken(tokens.access_token)

      try {
        const user = await authApi.me()
        return { tokens, user }
      } catch (error) {
        tokenStorage.clearAccessToken()
        throw error
      }
    },
    onSuccess: ({ tokens, user }) => {
      login({ accessToken: tokens.access_token, user })
    },
  })
}
