import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import faceScanImage from '@/assets/images/face-scan.svg'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { routePaths } from '@/constants/routes'
import { useConfirmPasswordReset } from '@/features/auth/hooks/useConfirmPasswordReset'
import { useRequestPasswordResetOtp } from '@/features/auth/hooks/useRequestPasswordResetOtp'
import { useVerifyPasswordResetOtp } from '@/features/auth/hooks/useVerifyPasswordResetOtp'
import {
  confirmPasswordResetSchema,
  requestOtpSchema,
  type ConfirmPasswordResetFormValues,
  type RequestOtpFormValues,
  type VerifyOtpFormValues,
  verifyOtpSchema,
} from '@/features/auth/schemas/password-reset.schema'
import { getApiErrorMessage } from '@/lib/utils'

type ResetStep = 'request-otp' | 'verify-otp' | 'set-password' | 'done'

function formatTtl(seconds: number | null): string {
  if (!seconds) {
    return ''
  }

  const minutes = Math.floor(seconds / 60)
  const restSeconds = seconds % 60
  return `${minutes} phút ${restSeconds.toString().padStart(2, '0')} giây`
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [step, setStep] = useState<ResetStep>('request-otp')
  const [otpTtl, setOtpTtl] = useState<number | null>(null)
  const [resetTokenTtl, setResetTokenTtl] = useState<number | null>(null)
  const requestOtp = useRequestPasswordResetOtp()
  const verifyOtp = useVerifyPasswordResetOtp()
  const confirmReset = useConfirmPasswordReset()

  const requestForm = useForm<RequestOtpFormValues>({
    resolver: zodResolver(requestOtpSchema),
    defaultValues: { email: '' },
  })
  const otpForm = useForm<VerifyOtpFormValues>({
    resolver: zodResolver(verifyOtpSchema),
    defaultValues: { otp: '' },
  })
  const passwordForm = useForm<ConfirmPasswordResetFormValues>({
    resolver: zodResolver(confirmPasswordResetSchema),
    defaultValues: { confirmPassword: '', newPassword: '' },
  })

  const handleRequestOtp = (values: RequestOtpFormValues) => {
    requestOtp.mutate(values, {
      onSuccess: (response) => {
        setEmail(values.email)
        setOtpTtl(response.otp_ttl_seconds)
        setStep('verify-otp')
      },
    })
  }

  const handleVerifyOtp = (values: VerifyOtpFormValues) => {
    verifyOtp.mutate(
      { email, otp: values.otp },
      {
        onSuccess: (response) => {
          setResetToken(response.reset_token)
          setResetTokenTtl(response.reset_token_ttl_seconds)
          setStep('set-password')
        },
      },
    )
  }

  const handleConfirmReset = (values: ConfirmPasswordResetFormValues) => {
    confirmReset.mutate(
      { new_password: values.newPassword, reset_token: resetToken },
      {
        onSuccess: () => {
          setStep('done')
          passwordForm.reset()
        },
      },
    )
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="login-panel__visual">
          <img src={faceScanImage} alt="" />
        </div>
        <div className="login-panel__form">
          <p className="eyebrow">Password reset</p>
          <h1>Quên mật khẩu</h1>
          <div className="reset-steps" aria-label="Các bước đặt lại mật khẩu">
            <span className={step === 'request-otp' ? 'reset-steps__item reset-steps__item--active' : 'reset-steps__item'}>
              Email
            </span>
            <span className={step === 'verify-otp' ? 'reset-steps__item reset-steps__item--active' : 'reset-steps__item'}>
              OTP
            </span>
            <span className={step === 'set-password' ? 'reset-steps__item reset-steps__item--active' : 'reset-steps__item'}>
              Mật khẩu mới
            </span>
          </div>
          {step === 'request-otp' ? (
            <form className="form-stack" onSubmit={requestForm.handleSubmit(handleRequestOtp)}>
              <Input
                autoComplete="email"
                error={requestForm.formState.errors.email?.message}
                label="Email"
                placeholder="email@company.com"
                type="email"
                {...requestForm.register('email')}
              />
              {requestOtp.isError ? (
                <StatusMessage tone="error">
                  {getApiErrorMessage(requestOtp.error, 'Không thể gửi OTP đặt lại mật khẩu.')}
                </StatusMessage>
              ) : null}
              <Button isLoading={requestOtp.isPending} type="submit">
                Gửi OTP
              </Button>
            </form>
          ) : null}
          {step === 'verify-otp' ? (
            <form className="form-stack" onSubmit={otpForm.handleSubmit(handleVerifyOtp)}>
              <StatusMessage>
                OTP đã được gửi tới {email}. {formatTtl(otpTtl) ? `Hiệu lực trong ${formatTtl(otpTtl)}.` : ''}
              </StatusMessage>
              <Input
                autoComplete="one-time-code"
                error={otpForm.formState.errors.otp?.message}
                inputMode="numeric"
                label="OTP"
                maxLength={6}
                placeholder="123456"
                {...otpForm.register('otp')}
              />
              {verifyOtp.isError ? (
                <StatusMessage tone="error">
                  {getApiErrorMessage(verifyOtp.error, 'OTP không hợp lệ hoặc đã hết hạn.')}
                </StatusMessage>
              ) : null}
              <Button isLoading={verifyOtp.isPending} type="submit">
                Xác thực OTP
              </Button>
              <Button
                onClick={() => setStep('request-otp')}
                type="button"
                variant="secondary"
              >
                Đổi email
              </Button>
            </form>
          ) : null}
          {step === 'set-password' ? (
            <form className="form-stack" onSubmit={passwordForm.handleSubmit(handleConfirmReset)}>
              <StatusMessage>
                Token đặt lại mật khẩu đã sẵn sàng. {formatTtl(resetTokenTtl) ? `Hiệu lực trong ${formatTtl(resetTokenTtl)}.` : ''}
              </StatusMessage>
              <Input
                autoComplete="new-password"
                error={passwordForm.formState.errors.newPassword?.message}
                label="Mật khẩu mới"
                type="password"
                {...passwordForm.register('newPassword')}
              />
              <Input
                autoComplete="new-password"
                error={passwordForm.formState.errors.confirmPassword?.message}
                label="Nhập lại mật khẩu"
                type="password"
                {...passwordForm.register('confirmPassword')}
              />
              {confirmReset.isError ? (
                <StatusMessage tone="error">
                  {getApiErrorMessage(confirmReset.error, 'Không thể đặt lại mật khẩu.')}
                </StatusMessage>
              ) : null}
              <Button isLoading={confirmReset.isPending} type="submit">
                Đặt lại mật khẩu
              </Button>
            </form>
          ) : null}
          {step === 'done' ? (
            <div className="form-stack">
              <StatusMessage tone="success">
                Đặt lại mật khẩu thành công. Bạn có thể đăng nhập bằng mật khẩu mới.
              </StatusMessage>
              <Link className="button button--primary button--md" to={routePaths.login}>
                <span>Quay lại đăng nhập</span>
              </Link>
            </div>
          ) : null}
          {step !== 'done' ? (
            <Link className="auth-link" to={routePaths.login}>
              Quay lại đăng nhập
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  )
}
