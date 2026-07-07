import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { routePaths } from '@/constants/routes'
import { useLogout } from '@/features/auth/hooks/useLogout'
import { getInitials } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth.store'

export function Header() {
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  const logoutMutation = useLogout()

  const handleLogout = () => {
    logoutMutation.mutate(undefined, {
      onSettled: () => navigate(routePaths.login, { replace: true }),
    })
  }

  return (
    <header className="header">
      <div>
        <p className="eyebrow">Dashboard</p>
        <h1>Agentic RAG</h1>
      </div>
      <div className="header__account">
        <div className="avatar" aria-hidden="true">
          {getInitials(user?.email)}
        </div>
        <div className="header__user">
          <strong>{user?.email ?? 'Đang xác thực'}</strong>
          <span>{user?.role_name ?? 'unknown'}</span>
        </div>
        <Button
          isLoading={logoutMutation.isPending}
          onClick={handleLogout}
          size="sm"
          variant="secondary"
        >
          Đăng xuất
        </Button>
      </div>
    </header>
  )
}
