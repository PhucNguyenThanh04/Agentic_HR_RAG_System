import { zodResolver } from '@hookform/resolvers/zod'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import faceScanImage from '@/assets/images/face-scan.svg'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { routePaths } from '@/constants/routes'
import { useLogin } from '@/features/auth/hooks/useLogin'
import { loginSchema, type LoginFormValues } from '@/features/auth/schemas/login.schema'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth.store'

export function LoginPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const navigate = useNavigate()
  const loginMutation = useLogin()
  const {
    formState: { errors },
    handleSubmit,
    register,
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  if (isAuthenticated) {
    return <Navigate to={routePaths.dashboard} replace />
  }

  const onSubmit = (values: LoginFormValues) => {
    loginMutation.mutate(values, {
      onSuccess: () => {
        navigate(routePaths.dashboard, { replace: true })
      },
    })
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="login-panel__visual">
          <img src={faceScanImage} alt="" />
        </div>
        <div className="login-panel__form">
          <p className="eyebrow">Face Attendance</p>
          <h1>Đăng nhập hệ thống</h1>
          <form className="form-stack" onSubmit={handleSubmit(onSubmit)}>
            <Input
              autoComplete="email"
              error={errors.email?.message}
              label="Email"
              placeholder="admin@example.com"
              type="email"
              {...register('email')}
            />
            <Input
              autoComplete="current-password"
              error={errors.password?.message}
              label="Mật khẩu"
              placeholder="Nhập mật khẩu"
              type="password"
              {...register('password')}
            />
            <Link className="auth-link" to={routePaths.forgotPassword}>
              Quên mật khẩu?
            </Link>
            {loginMutation.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(loginMutation.error, 'Đăng nhập không thành công.')}
              </StatusMessage>
            ) : null}
            <Button isLoading={loginMutation.isPending} type="submit">
              Đăng nhập
            </Button>
          </form>
        </div>
      </section>
    </main>
  )
}
