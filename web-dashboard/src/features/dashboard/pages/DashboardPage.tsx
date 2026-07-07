import { Link, Navigate } from 'react-router-dom'
import { AccessDeniedPanel } from '@/components/layout/AccessDeniedPanel'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { routePaths } from '@/constants/routes'
import { useDepartments } from '@/features/departments/hooks/useDepartments'
import { useEmployees } from '@/features/employees/hooks/useEmployees'
import { EmployeeTable } from '@/features/employees/components/EmployeeTable'
import { useFaceProfiles } from '@/features/face-profiles/hooks/useFaceProfiles'
import { usePositions } from '@/features/positions/hooks/usePositions'
import { formatNumber, getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth.store'
import type { RoleName } from '@/types/common.types'

const roleCopy: Record<Exclude<RoleName, 'employee'>, {
  actionLabel: string
  actionPath: string
  description: string
  eyebrow: string
  title: string
}> = {
  admin: {
    actionLabel: 'Cài đặt hệ thống',
    actionPath: routePaths.settings,
    description: 'Quản trị toàn bộ nhân sự, phân quyền, danh mục, nhận diện và audit nghiệp vụ.',
    eyebrow: 'Admin',
    title: 'Admin dashboard',
  },
  hr: {
    actionLabel: 'Onboarding nhân viên',
    actionPath: routePaths.onboarding,
    description: 'Theo dõi nhân sự, đăng ký khuôn mặt, chấm công, nghỉ phép và điều chỉnh công.',
    eyebrow: 'HR',
    title: 'HR dashboard',
  },
  manager: {
    actionLabel: 'Xem team',
    actionPath: routePaths.employees,
    description: 'Theo dõi chấm công team, đơn nghỉ đang chờ duyệt và yêu cầu sửa công cần xác nhận.',
    eyebrow: 'Manager',
    title: 'Manager dashboard',
  },
}

export function DashboardPage() {
  const role = useAuthStore((state) => state.user?.role_name)
  const canAccessDashboard = role === 'admin' || role === 'hr' || role === 'manager'
  const dashboardCopy = canAccessDashboard ? roleCopy[role] : null
  const employeesQuery = useEmployees({ page: 1, page_size: 6 }, canAccessDashboard)
  const departmentsQuery = useDepartments(undefined, canAccessDashboard)
  const positionsQuery = usePositions(undefined, canAccessDashboard)
  const faceProfilesQuery = useFaceProfiles({ page: 1, page_size: 1 }, canAccessDashboard)
  const employees = employeesQuery.data?.items ?? []
  const departmentNames = new Map((departmentsQuery.data ?? []).map((department) => [department.department_id, department.name]))
  const positionNames = new Map((positionsQuery.data ?? []).map((position) => [position.position_id, position.name]))

  if (role === 'employee') {
    return <Navigate to={routePaths.chatbox} replace />
  }

  if (!canAccessDashboard || !dashboardCopy) {
    return <AccessDeniedPanel />
  }

  return (
    <section className="page-stack">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">{dashboardCopy.eyebrow}</p>
          <h2>{dashboardCopy.title}</h2>
          <p>{dashboardCopy.description}</p>
        </div>
        <Link className="button button--primary button--md" to={dashboardCopy.actionPath}>
          <span>{dashboardCopy.actionLabel}</span>
        </Link>
      </div>
      <div className="stat-grid">
        <article className="stat-card stat-card--teal">
          <span>{role === 'manager' ? 'Nhân viên team' : 'Nhân viên'}</span>
          <strong>{formatNumber(employeesQuery.data?.total ?? 0)}</strong>
        </article>
        <article className="stat-card stat-card--blue">
          <span>{role === 'manager' ? 'Đã check-in hôm nay' : 'Phòng ban'}</span>
          <strong>{formatNumber(departmentsQuery.data?.length ?? 0)}</strong>
        </article>
        <article className="stat-card stat-card--amber">
          <span>{role === 'manager' ? 'Đơn nghỉ chờ duyệt' : 'Chức vụ'}</span>
          <strong>{formatNumber(positionsQuery.data?.length ?? 0)}</strong>
        </article>
        <article className="stat-card stat-card--gray">
          <span>{role === 'manager' ? 'Yêu cầu sửa công' : 'Face profiles'}</span>
          <strong>{formatNumber(faceProfilesQuery.data?.total ?? 0)}</strong>
        </article>
      </div>
      {role === 'manager' ? (
        <StatusMessage>
          Các số liệu team đang dùng dữ liệu backend hiện có. Khi backend expose endpoint team-scoped, dashboard manager sẽ lọc theo manager trực tiếp.
        </StatusMessage>
      ) : null}
      {employeesQuery.isLoading ? <Loading /> : null}
      {employeesQuery.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(employeesQuery.error, 'Không thể tải dữ liệu tổng quan.')}
        </StatusMessage>
      ) : null}
      {employees.length > 0 ? (
        <section className="panel">
          <div className="panel__header">
            <h2>Nhân viên mới nhất</h2>
            <Link to={routePaths.employees}>Xem tất cả</Link>
          </div>
          <EmployeeTable
            departmentNames={departmentNames}
            employees={employees}
            positionNames={positionNames}
          />
        </section>
      ) : null}
    </section>
  )
}
