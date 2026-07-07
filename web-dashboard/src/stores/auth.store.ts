import { create } from 'zustand'
import type { AuthUser } from '@/features/auth/types/auth.types'
import { tokenStorage } from '@/lib/storage'

type LoginSession = {
  accessToken: string
  user: AuthUser
}

type AuthState = {
  accessToken: string | null
  isAuthenticated: boolean
  login: (session: LoginSession) => void
  logout: () => void
  setAccessToken: (token: string) => void
  setUser: (user: AuthUser | null) => void
  user: AuthUser | null
}

const storedToken = tokenStorage.getAccessToken()

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: storedToken,
  isAuthenticated: Boolean(storedToken),
  user: null,
  login: ({ accessToken, user }) => {
    tokenStorage.setAccessToken(accessToken)
    set({ accessToken, isAuthenticated: true, user })
  },
  logout: () => {
    tokenStorage.clearAccessToken()
    set({ accessToken: null, isAuthenticated: false, user: null })
  },
  setAccessToken: (token) => {
    tokenStorage.setAccessToken(token)
    set({ accessToken: token, isAuthenticated: true })
  },
  setUser: (user) => set({ user }),
}))
