import { NavLink } from 'react-router-dom'
import { getNavigationItemsForRole } from '@/constants/routes'
import { useAuthStore } from '@/stores/auth.store'

export function Sidebar() {
  const role = useAuthStore((state) => state.user?.role_name)
  const navigationItems = getNavigationItemsForRole(role)

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <span className="sidebar__brand-mark">FA</span>
        <span>
          <strong>Face Attendance</strong>
          <small>Management System</small>
        </span>
      </div>
      <nav className="sidebar__nav" aria-label="Điều hướng chính">
        {navigationItems.length > 0 ? (
          navigationItems.map((item) => (
            <NavLink
              className={({ isActive }) => (isActive ? 'sidebar__link sidebar__link--active' : 'sidebar__link')}
              end={item.path === '/'}
              key={item.path}
              to={item.path}
            >
              {item.label}
            </NavLink>
          ))
        ) : (
          <span className="sidebar__empty">Không có dashboard web</span>
        )}
      </nav>
    </aside>
  )
}
