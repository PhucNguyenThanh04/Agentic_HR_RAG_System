import { useQuery } from '@tanstack/react-query'
import { authApi } from '@/features/auth/api/auth.api'

export function useMe(enabled = true) {
  return useQuery({
    enabled,
    queryFn: authApi.me,
    queryKey: ['auth', 'me'],
  })
}
