import { api } from '@/lib/axios'
import type { MessageResponse } from '@/types/common.types'
import type {
  AuthUser,
  LoginPayload,
  PasswordResetConfirmPayload,
  PasswordResetConfirmResponse,
  PasswordResetRequestOtpPayload,
  PasswordResetRequestOtpResponse,
  PasswordResetVerifyOtpPayload,
  PasswordResetVerifyOtpResponse,
  TokenPairResponse,
} from '@/features/auth/types/auth.types'

export const authApi = {
  login: async (payload: LoginPayload): Promise<TokenPairResponse> => {
    const response = await api.post<TokenPairResponse>('/auth/login', payload)
    return response.data
  },
  me: async (): Promise<AuthUser> => {
    const response = await api.get<AuthUser>('/auth/me')
    return response.data
  },
  logout: async (): Promise<MessageResponse> => {
    const response = await api.post<MessageResponse>('/auth/logout')
    return response.data
  },
  requestPasswordResetOtp: async (
    payload: PasswordResetRequestOtpPayload,
  ): Promise<PasswordResetRequestOtpResponse> => {
    const response = await api.post<PasswordResetRequestOtpResponse>(
      '/auth/password-reset/request-otp',
      payload,
    )
    return response.data
  },
  verifyPasswordResetOtp: async (
    payload: PasswordResetVerifyOtpPayload,
  ): Promise<PasswordResetVerifyOtpResponse> => {
    const response = await api.post<PasswordResetVerifyOtpResponse>(
      '/auth/password-reset/verify-otp',
      payload,
    )
    return response.data
  },
  confirmPasswordReset: async (
    payload: PasswordResetConfirmPayload,
  ): Promise<PasswordResetConfirmResponse> => {
    const response = await api.post<PasswordResetConfirmResponse>(
      '/auth/password-reset/confirm',
      payload,
    )
    return response.data
  },
}
