import type { ReactNode } from 'react'
import { AccessDeniedPanel } from '@/components/layout/AccessDeniedPanel'
import type { RoleName } from '@/types/common.types'
import { useAuthStore } from '@/stores/auth.store'

type RoleRouteProps = {
  allowedRoles: RoleName[]
  children: ReactNode
}

export function RoleRoute({ allowedRoles, children }: RoleRouteProps) {
  const role = useAuthStore((state) => state.user?.role_name)

  if (!role || !allowedRoles.includes(role)) {
    return <AccessDeniedPanel />
  }

  return children
}
