import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { routePaths } from '@/constants/routes'
import { useMe } from '@/features/auth/hooks/useMe'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth.store'

export function AppLayout() {
  const accessToken = useAuthStore((state) => state.accessToken)
  const logout = useAuthStore((state) => state.logout)
  const navigate = useNavigate()
  const setUser = useAuthStore((state) => state.setUser)
  const user = useAuthStore((state) => state.user)
  const meQuery = useMe(Boolean(accessToken && !user))
  const isResolvingUser = Boolean(accessToken && !user && meQuery.isLoading)

  useEffect(() => {
    if (meQuery.data) {
      setUser(meQuery.data)
    }
  }, [meQuery.data, setUser])

  useEffect(() => {
    if (meQuery.isError) {
      logout()
      navigate(routePaths.login, { replace: true })
    }
  }, [logout, meQuery.isError, navigate])

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <Header />
        <main className="content">
          {isResolvingUser ? <Loading label="Đang tải hồ sơ đăng nhập" /> : null}
          {meQuery.isError ? (
            <StatusMessage tone="error">
              {getApiErrorMessage(meQuery.error, 'Không thể tải hồ sơ đăng nhập.')}
            </StatusMessage>
          ) : null}
          {!isResolvingUser ? <Outlet /> : null}
        </main>
      </div>
    </div>
  )
}
