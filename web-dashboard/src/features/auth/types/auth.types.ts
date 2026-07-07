import type { RoleName, UserStatus, UUID } from '@/types/common.types'

export type LoginPayload = {
  email: string
  password: string
}

export type TokenPairResponse = {
  access_token: string
  access_token_expires_at: string
  refresh_token: string
  refresh_token_expires_at: string
  token_type: 'bearer'
}

export type AuthUser = {
  user_id: UUID
  email: string
  role_name: RoleName
  status: UserStatus
  token_version: number
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export type LoginResult = {
  tokens: TokenPairResponse
  user: AuthUser
}

export type PasswordResetRequestOtpPayload = {
  email: string
}

export type PasswordResetRequestOtpResponse = {
  message: string
  otp_ttl_seconds: number
}

export type PasswordResetVerifyOtpPayload = {
  email: string
  otp: string
}

export type PasswordResetVerifyOtpResponse = {
  reset_token: string
  reset_token_ttl_seconds: number
}

export type PasswordResetConfirmPayload = {
  reset_token: string
  new_password: string
}

export type PasswordResetConfirmResponse = {
  message: string
}
