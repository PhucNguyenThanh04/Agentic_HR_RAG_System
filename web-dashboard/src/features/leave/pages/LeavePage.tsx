import { useMemo, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Loading } from '@/components/ui/Loading'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { Pagination } from '@/components/ui/Pagination'
import { useAuthStore } from '@/stores/auth.store'
import { useEmployees, useMyEmployeeProfile } from '@/features/employees/hooks/useEmployees'
import {
  useLeaveRequests,
  useLeaveTypes,
  useLeaveBalance,
  useCancelLeaveRequest,
} from '../hooks/useLeave'
import { LeaveBalanceSummary } from '../components/LeaveBalanceSummary'
import { LeaveRequestTable } from '../components/LeaveRequestTable'
import { LeaveRequestFormModal } from '../components/LeaveRequestFormModal'
import { ReviewLeaveRequestModal } from '../components/ReviewLeaveRequestModal'
import { getApiErrorMessage } from '@/lib/utils'
import type { LeaveRequest, LeaveRequestStatus } from '../types/leave.types'

export function LeavePage() {
  const role = useAuthStore((state) => state.user?.role_name)
  const isEmployee = role === 'employee'

  // Tab state for staff: 'team' (default) or 'personal'
  const [viewMode, setViewMode] = useState<'team' | 'personal'>(isEmployee ? 'personal' : 'team')

  // Modals state
  const [isRequestFormOpen, setIsRequestFormOpen] = useState(false)
  const [requestToReview, setRequestToReview] = useState<LeaveRequest | null>(null)

  // Filters state - Personal View
  const [myStatusFilter, setMyStatusFilter] = useState<LeaveRequestStatus | ''>('')
  const [myTypeFilter, setMyTypeFilter] = useState<string>('')
  const [myPage, setMyPage] = useState(1)

  // Filters state - Team View
  const [teamStatusFilter, setTeamStatusFilter] = useState<LeaveRequestStatus | ''>('')
  const [teamEmployeeFilter, setTeamEmployeeFilter] = useState<string>('')
  const [teamTypeFilter, setTeamTypeFilter] = useState<string>('')
  const [teamPage, setTeamPage] = useState(1)

  // Load queries
  const myProfileQuery = useMyEmployeeProfile()
  const myEmployeeId = myProfileQuery.data?.employee_id

  // 1. Personal data
  const myBalanceQuery = useLeaveBalance(myEmployeeId)
  const myRequestsQuery = useLeaveRequests(
    {
      employee_id: myEmployeeId,
      status: myStatusFilter || undefined,
      leave_type_id: myTypeFilter ? Number(myTypeFilter) : undefined,
      page: myPage,
      page_size: 10,
    },
    Boolean(myEmployeeId)
  )

  // 2. Team/Staff data
  const teamRequestsQuery = useLeaveRequests(
    {
      status: teamStatusFilter || undefined,
      employee_id: teamEmployeeFilter || undefined,
      leave_type_id: teamTypeFilter ? Number(teamTypeFilter) : undefined,
      page: teamPage,
      page_size: 10,
    },
    !isEmployee && viewMode === 'team'
  )

  const employeesQuery = useEmployees(
    { page: 1, page_size: 200, status: 'active' },
    !isEmployee
  )

  // 3. Metadata list
  const leaveTypesQuery = useLeaveTypes()

  // Mappers
  const employeeNames = useMemo(() => {
    const map = new Map<string, string>()
    if (employeesQuery.data?.items) {
      employeesQuery.data.items.forEach((emp) => {
        map.set(emp.employee_id, emp.full_name)
      })
    }
    if (myProfileQuery.data) {
      map.set(myProfileQuery.data.employee_id, myProfileQuery.data.full_name)
    }
    return map
  }, [employeesQuery.data?.items, myProfileQuery.data])

  const leaveTypeNames = useMemo(() => {
    const map = new Map<number, string>()
    if (leaveTypesQuery.data) {
      leaveTypesQuery.data.forEach((t) => {
        map.set(t.leave_type_id, t.name)
      })
    }
    return map
  }, [leaveTypesQuery.data])

  // Cancel leave request mutation
  const cancelMutation = useCancelLeaveRequest()

  const handleCancelRequest = (requestId: string) => {
    if (window.confirm('Bạn có chắc chắn muốn hủy yêu cầu nghỉ phép này?')) {
      cancelMutation.mutate(requestId)
    }
  }

  // Loading state
  const isPersonalLoading = myProfileQuery.isLoading || myBalanceQuery.isLoading || myRequestsQuery.isLoading
  const isTeamLoading = teamRequestsQuery.isLoading || employeesQuery.isLoading

  return (
    <section className="page-stack">
      <PageHeader
        actions={
          myProfileQuery.data ? (
            <Button onClick={() => setIsRequestFormOpen(true)} variant="primary">
              Đăng ký nghỉ phép
            </Button>
          ) : null
        }
        description="Quản lý và phê duyệt đơn nghỉ phép của bạn hoặc nhân viên cấp dưới."
        eyebrow="Human resources"
        title="Nghỉ phép"
      />

      {/* Tab toggle buttons for manager/hr/admin */}
      {!isEmployee ? (
        <div className="toolbar toolbar--compact" style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
          <Button
            onClick={() => setViewMode('team')}
            variant={viewMode === 'team' ? 'primary' : 'secondary'}
          >
            Quản lý đơn team
          </Button>
          <Button
            onClick={() => setViewMode('personal')}
            variant={viewMode === 'personal' ? 'primary' : 'secondary'}
          >
            Cá nhân
          </Button>
        </div>
      ) : null}

      {/* --- Personal View Mode --- */}
      {viewMode === 'personal' ? (
        <div className="page-grid">
          {/* Main content: list of personal requests */}
          <div className="page-stack">
            <div className="panel">
              <div className="panel__header">
                <h2>Lịch sử yêu cầu nghỉ phép</h2>
              </div>

              {/* Filters */}
              <div className="toolbar toolbar--compact" style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
                <Select
                  label="Trạng thái"
                  onChange={(e) => {
                    setMyStatusFilter(e.target.value as LeaveRequestStatus | '')
                    setMyPage(1)
                  }}
                  value={myStatusFilter}
                >
                  <option value="">Tất cả trạng thái</option>
                  <option value="pending">Chờ duyệt</option>
                  <option value="approved">Đã duyệt</option>
                  <option value="rejected">Từ chối</option>
                  <option value="cancelled">Đã hủy</option>
                </Select>

                <Select
                  label="Loại phép"
                  onChange={(e) => {
                    setMyTypeFilter(e.target.value)
                    setMyPage(1)
                  }}
                  value={myTypeFilter}
                >
                  <option value="">Tất cả loại phép</option>
                  {leaveTypesQuery.data?.map((t) => (
                    <option key={t.leave_type_id} value={t.leave_type_id}>
                      {t.name}
                    </option>
                  ))}
                </Select>
              </div>

              {isPersonalLoading ? <Loading /> : null}

              {myRequestsQuery.isError ? (
                <StatusMessage tone="error">
                  {getApiErrorMessage(myRequestsQuery.error, 'Không thể tải danh sách đơn nghỉ phép.')}
                </StatusMessage>
              ) : null}

              {!isPersonalLoading && !myRequestsQuery.isError && (myRequestsQuery.data?.items ?? []).length === 0 ? (
                <EmptyState description="Gửi yêu cầu phép bằng nút ở góc trên." title="Chưa có yêu cầu nghỉ phép nào" />
              ) : null}

              {myRequestsQuery.data?.items && myRequestsQuery.data.items.length > 0 ? (
                <>
                  <LeaveRequestTable
                    employeeNames={employeeNames}
                    isCancelling={cancelMutation.isPending}
                    leaveTypeNames={leaveTypeNames}
                    onCancel={handleCancelRequest}
                    requests={myRequestsQuery.data.items}
                  />
                  <Pagination
                    currentPage={myRequestsQuery.data.page}
                    isFetching={myRequestsQuery.isFetching}
                    onPageChange={setMyPage}
                    pageSize={myRequestsQuery.data.page_size}
                    total={myRequestsQuery.data.total}
                  />
                </>
              ) : null}
            </div>
          </div>

          {/* Sidebar: Personal balance details */}
          <aside className="side-stack">
            <section className="side-panel">
              <h2>Số dư nghỉ phép của bạn</h2>
              <LeaveBalanceSummary
                balance={myBalanceQuery.data}
                isLoading={myBalanceQuery.isLoading}
              />
            </section>
          </aside>
        </div>
      ) : null}

      {/* --- Team View Mode (Manager / HR / Admin) --- */}
      {viewMode === 'team' ? (
        <div className="page-stack">
          <div className="panel">
            <div className="panel__header">
              <h2>Danh sách yêu cầu nghỉ phép của nhân viên</h2>
            </div>

            {/* Filters */}
            <div className="toolbar toolbar--compact" style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
              <Select
                label="Nhân viên"
                onChange={(e) => {
                  setTeamEmployeeFilter(e.target.value)
                  setTeamPage(1)
                }}
                value={teamEmployeeFilter}
              >
                <option value="">Tất cả nhân viên</option>
                {employeesQuery.data?.items.map((emp) => (
                  <option key={emp.employee_id} value={emp.employee_id}>
                    {emp.employee_code} - {emp.full_name}
                  </option>
                ))}
              </Select>

              <Select
                label="Trạng thái"
                onChange={(e) => {
                  setTeamStatusFilter(e.target.value as LeaveRequestStatus | '')
                  setTeamPage(1)
                }}
                value={teamStatusFilter}
              >
                <option value="">Tất cả trạng thái</option>
                <option value="pending">Chờ duyệt</option>
                <option value="approved">Đã duyệt</option>
                <option value="rejected">Từ chối</option>
                <option value="cancelled">Đã hủy</option>
              </Select>

              <Select
                label="Loại phép"
                onChange={(e) => {
                  setTeamTypeFilter(e.target.value)
                  setTeamPage(1)
                }}
                value={teamTypeFilter}
              >
                <option value="">Tất cả loại phép</option>
                {leaveTypesQuery.data?.map((t) => (
                  <option key={t.leave_type_id} value={t.leave_type_id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            </div>

            {isTeamLoading ? <Loading /> : null}

            {teamRequestsQuery.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(teamRequestsQuery.error, 'Không thể tải yêu cầu nghỉ phép của team.')}
              </StatusMessage>
            ) : null}

            {!isTeamLoading && !teamRequestsQuery.isError && (teamRequestsQuery.data?.items ?? []).length === 0 ? (
              <EmptyState title="Không tìm thấy yêu cầu nghỉ phép nào từ nhân viên" />
            ) : null}

            {teamRequestsQuery.data?.items && teamRequestsQuery.data.items.length > 0 ? (
              <>
                <LeaveRequestTable
                  employeeNames={employeeNames}
                  leaveTypeNames={leaveTypeNames}
                  onReview={(req) => setRequestToReview(req)}
                  requests={teamRequestsQuery.data.items}
                  showEmployeeColumn={true}
                />
                <Pagination
                  currentPage={teamRequestsQuery.data.page}
                  isFetching={teamRequestsQuery.isFetching}
                  onPageChange={setTeamPage}
                  pageSize={teamRequestsQuery.data.page_size}
                  total={teamRequestsQuery.data.total}
                />
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* --- Modals --- */}
      <LeaveRequestFormModal
        isOpen={isRequestFormOpen}
        onClose={() => setIsRequestFormOpen(false)}
      />

      <ReviewLeaveRequestModal
        employeeName={requestToReview ? employeeNames.get(requestToReview.employee_id) || 'Nhân viên' : ''}
        isOpen={Boolean(requestToReview)}
        leaveTypeName={requestToReview ? leaveTypeNames.get(requestToReview.leave_type_id) || 'Loại phép' : ''}
        onClose={() => setRequestToReview(null)}
        request={requestToReview}
      />
    </section>
  )
}
