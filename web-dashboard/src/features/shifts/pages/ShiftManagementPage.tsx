import { useMemo, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Loading } from '@/components/ui/Loading'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useEmployees } from '@/features/employees/hooks/useEmployees'
import { AssignShiftForm } from '@/features/shifts/components/AssignShiftForm'
import { ChangeShiftModal } from '@/features/shifts/components/ChangeShiftModal'
import { EmployeeShiftAssignmentPanel } from '@/features/shifts/components/EmployeeShiftAssignmentPanel'
import { WorkShiftForm } from '@/features/shifts/components/WorkShiftForm'
import { WorkShiftTable } from '@/features/shifts/components/WorkShiftTable'
import { useToggleWorkShift } from '@/features/shifts/hooks/useToggleWorkShift'
import { useWorkShifts } from '@/features/shifts/hooks/useWorkShifts'
import type {
  EmployeeShiftAssignment,
  WorkShift,
} from '@/features/shifts/types/shift.types'
import { getApiErrorMessage } from '@/lib/utils'
import { useAuthStore } from '@/stores/auth.store'

const EMPLOYEE_PAGE_SIZE = 200

export function ShiftManagementPage() {
  const role = useAuthStore((state) => state.user?.role_name)
  const canManageShifts = role === 'admin'
  const canManageAssignments = role === 'admin' || role === 'hr'
  const [assignmentBeingEdited, setAssignmentBeingEdited] =
    useState<EmployeeShiftAssignment | null>(null)
  const [isActiveFilter, setIsActiveFilter] = useState('')
  const [isChangeShiftOpen, setIsChangeShiftOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('')
  const [shiftBeingEdited, setShiftBeingEdited] = useState<WorkShift | null>(null)

  const workShiftsQuery = useWorkShifts({
    is_active: isActiveFilter === '' ? undefined : isActiveFilter === 'active',
    search: search || undefined,
  })
  const employeesQuery = useEmployees({
    page: 1,
    page_size: EMPLOYEE_PAGE_SIZE,
    status: 'active',
  })
  const employees = useMemo(() => employeesQuery.data?.items ?? [], [employeesQuery.data?.items])
  const shifts = useMemo(() => workShiftsQuery.data ?? [], [workShiftsQuery.data])
  const selectedEmployeeIdForQuery = selectedEmployeeId || employees[0]?.employee_id || ''
  const toggleWorkShift = useToggleWorkShift()

  const shiftMap = useMemo(
    () => new Map(shifts.map((shift) => [shift.shift_id, shift])),
    [shifts],
  )

  const handleToggleShift = (shift: WorkShift) => {
    const actionLabel = shift.is_active ? 'tắt' : 'bật'
    const shouldToggle = window.confirm(`Bạn muốn ${actionLabel} ca làm việc này?`)

    if (shouldToggle) {
      toggleWorkShift.mutate(
        { isActive: shift.is_active, shiftId: shift.shift_id },
        {
          onSuccess: () => {
            if (shiftBeingEdited?.shift_id === shift.shift_id) {
              setShiftBeingEdited(null)
            }
          },
        },
      )
    }
  }

  return (
    <section className="page-grid">
      <div className="page-stack">
        <PageHeader
          actions={
            canManageAssignments ? (
              <Button onClick={() => setIsChangeShiftOpen(true)} variant="secondary">
                Đổi ca
              </Button>
            ) : null
          }
          description="Quản lý ca làm việc và phân công ca theo endpoint /work-shifts, /shift-assignments."
          eyebrow="Attendance"
          title="Ca làm việc"
        />
        <div className="toolbar">
          <Input
            label="Tìm kiếm ca"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tên hoặc mã ca"
            value={search}
          />
          <Select
            label="Trạng thái"
            onChange={(event) => setIsActiveFilter(event.target.value)}
            value={isActiveFilter}
          >
            <option value="">Tất cả</option>
            <option value="active">Hoạt động</option>
            <option value="inactive">Tạm ngưng</option>
          </Select>
        </div>
        {workShiftsQuery.isLoading ? <Loading /> : null}
        {workShiftsQuery.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(workShiftsQuery.error, 'Không thể tải danh sách ca làm việc.')}
          </StatusMessage>
        ) : null}
        {toggleWorkShift.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(toggleWorkShift.error, 'Không thể cập nhật trạng thái ca làm việc.')}
          </StatusMessage>
        ) : null}
        {!workShiftsQuery.isLoading && !workShiftsQuery.isError && shifts.length === 0 ? (
          <EmptyState title="Chưa có ca làm việc" />
        ) : null}
        {shifts.length > 0 ? (
          <WorkShiftTable
            canManage={canManageShifts}
            isToggling={toggleWorkShift.isPending}
            onEdit={setShiftBeingEdited}
            onToggle={handleToggleShift}
            shifts={shifts}
          />
        ) : null}

        {employeesQuery.isLoading ? <Loading /> : null}
        {employeesQuery.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(employeesQuery.error, 'Không thể tải danh sách nhân viên.')}
          </StatusMessage>
        ) : null}
        <EmployeeShiftAssignmentPanel
          canManage={canManageAssignments}
          employees={employees}
          onEditAssignment={setAssignmentBeingEdited}
          onEmployeeChange={(employeeId) => {
            setAssignmentBeingEdited(null)
            setSelectedEmployeeId(employeeId)
          }}
          selectedEmployeeId={selectedEmployeeIdForQuery}
          shiftMap={shiftMap}
        />
      </div>

      <aside className="side-stack">
        <section className="side-panel">
          <h2>{shiftBeingEdited ? 'Sửa ca làm việc' : 'Tạo ca làm việc'}</h2>
          {canManageShifts ? (
            <WorkShiftForm
              key={shiftBeingEdited?.shift_id ?? 'new-work-shift'}
              onCancelEdit={() => setShiftBeingEdited(null)}
              selectedShift={shiftBeingEdited}
            />
          ) : (
            <StatusMessage tone="info">
              Tài khoản hiện tại chỉ có quyền xem danh sách ca làm việc.
            </StatusMessage>
          )}
        </section>
        <section className="side-panel">
          <h2>{assignmentBeingEdited ? 'Sửa phân công ca' : 'Gán ca cho nhân viên'}</h2>
          {canManageAssignments ? (
            <AssignShiftForm
              key={assignmentBeingEdited?.assignment_id ?? selectedEmployeeIdForQuery}
              employees={employees}
              onCancelEdit={() => setAssignmentBeingEdited(null)}
              onEmployeeChange={(employeeId) => {
                setSelectedEmployeeId(employeeId)
                setAssignmentBeingEdited(null)
              }}
              selectedAssignment={assignmentBeingEdited}
              selectedEmployeeId={selectedEmployeeIdForQuery}
              shifts={shifts}
            />
          ) : (
            <StatusMessage tone="info">
              Tài khoản hiện tại chỉ có quyền xem phân công ca.
            </StatusMessage>
          )}
        </section>
      </aside>
      <ChangeShiftModal
        key={isChangeShiftOpen ? selectedEmployeeIdForQuery : 'closed-change-shift'}
        employees={employees}
        isOpen={isChangeShiftOpen}
        onClose={() => setIsChangeShiftOpen(false)}
        selectedEmployeeId={selectedEmployeeIdForQuery}
        shifts={shifts}
      />
    </section>
  )
}
