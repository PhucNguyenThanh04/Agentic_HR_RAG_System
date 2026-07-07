import { Navigate, Outlet } from 'react-router-dom'
import { routePaths } from '@/constants/routes'
import { useAuthStore } from '@/stores/auth.store'

export function ProtectedRoute() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  if (!isAuthenticated) {
    return <Navigate to={routePaths.login} replace />
  }

  return <Outlet />
}
