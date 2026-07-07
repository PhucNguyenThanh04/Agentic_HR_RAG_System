import { useQueries } from '@tanstack/react-query'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { Table } from '@/components/ui/Table'
import type { Employee } from '@/features/employees/types/employee.types'
import { shiftApi } from '@/features/shifts/api/shift.api'
import { useCloseShiftAssignment } from '@/features/shifts/hooks/useCloseShiftAssignment'
import { useDeleteShiftAssignment } from '@/features/shifts/hooks/useDeleteShiftAssignment'
import type {
  EmployeeShiftAssignment,
  WorkShift,
} from '@/features/shifts/types/shift.types'
import { formatDate, getApiErrorMessage } from '@/lib/utils'

type EmployeeShiftAssignmentPanelProps = {
  canManage: boolean
  employees: Employee[]
  onEditAssignment: (assignment: EmployeeShiftAssignment) => void
  onEmployeeChange: (employeeId: string) => void
  selectedEmployeeId: string
  shiftMap: Map<number, WorkShift>
}

type AssignmentStatus = 'current' | 'ended' | 'unassigned' | 'upcoming'

type EmployeeShiftRow = {
  assignment: EmployeeShiftAssignment | null
  employee: Employee
  status: AssignmentStatus
}

function getToday(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function getAssignmentStatus(assignment: EmployeeShiftAssignment | null): AssignmentStatus {
  if (!assignment) {
    return 'unassigned'
  }

  const today = getToday()

  if (assignment.effective_date > today) {
    return 'upcoming'
  }

  if (assignment.end_date && assignment.end_date < today) {
    return 'ended'
  }

  return 'current'
}

function getRelevantAssignment(assignments: EmployeeShiftAssignment[]): EmployeeShiftAssignment | null {
  const today = getToday()
  const current = assignments
    .filter((assignment) => assignment.effective_date <= today && (!assignment.end_date || assignment.end_date >= today))
    .sort((left, right) => right.effective_date.localeCompare(left.effective_date))[0]

  if (current) {
    return current
  }

  const upcoming = assignments
    .filter((assignment) => assignment.effective_date > today)
    .sort((left, right) => left.effective_date.localeCompare(right.effective_date))[0]

  if (upcoming) {
    return upcoming
  }

  return (
    assignments
      .filter((assignment) => assignment.end_date)
      .sort((left, right) => (right.end_date ?? '').localeCompare(left.end_date ?? ''))[0] ?? null
  )
}

function getStatusBadge(status: AssignmentStatus) {
  if (status === 'current') {
    return <Badge tone="green">Đang áp dụng</Badge>
  }

  if (status === 'upcoming') {
    return <Badge tone="blue">Sắp áp dụng</Badge>
  }

  if (status === 'ended') {
    return <Badge tone="gray">Đã kết thúc</Badge>
  }

  return <Badge tone="amber">Chưa gán ca</Badge>
}

function formatTime(value?: string): string {
  return value ? value.slice(0, 5) : '-'
}

export function EmployeeShiftAssignmentPanel({
  canManage,
  employees,
  onEditAssignment,
  onEmployeeChange,
  selectedEmployeeId,
  shiftMap,
}: EmployeeShiftAssignmentPanelProps) {
  const assignmentQueries = useQueries({
    queries: employees.map((employee) => ({
      enabled: Boolean(employee.employee_id),
      queryFn: () => shiftApi.listEmployeeShiftAssignments(employee.employee_id),
      queryKey: ['shift-assignments', employee.employee_id],
    })),
  })
  const selectedEmployeeForMutation =
    selectedEmployeeId || assignmentQueries.find((query) => query.data?.[0])?.data?.[0]?.employee_id
  const closeAssignment = useCloseShiftAssignment(selectedEmployeeForMutation)
  const deleteAssignment = useDeleteShiftAssignment(selectedEmployeeForMutation)
  const isLoading = assignmentQueries.some((query) => query.isLoading)
  const error = assignmentQueries.find((query) => query.isError)?.error
  const rows: EmployeeShiftRow[] = employees.map((employee, index) => {
    const assignment = getRelevantAssignment(assignmentQueries[index]?.data ?? [])
    return {
      assignment,
      employee,
      status: getAssignmentStatus(assignment),
    }
  })

  const handleClose = (assignment: EmployeeShiftAssignment) => {
    const shouldClose = window.confirm('Đóng ca đang áp dụng này?')

    if (shouldClose) {
      onEmployeeChange(assignment.employee_id)
      closeAssignment.mutate(assignment.assignment_id)
    }
  }

  const handleDelete = (assignment: EmployeeShiftAssignment) => {
    const shouldDelete = window.confirm('Xóa phân công ca này?')

    if (shouldDelete) {
      onEmployeeChange(assignment.employee_id)
      deleteAssignment.mutate(assignment.assignment_id)
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Assignments</p>
          <h2>Ca làm của nhân viên</h2>
        </div>
      </div>
      {isLoading ? <Loading label="Đang tải ca làm của nhân viên" /> : null}
      {error ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(error, 'Không thể tải danh sách ca làm của nhân viên.')}
        </StatusMessage>
      ) : null}
      {closeAssignment.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(closeAssignment.error, 'Không thể đóng ca.')}
        </StatusMessage>
      ) : null}
      {deleteAssignment.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(deleteAssignment.error, 'Không thể xóa phân công ca.')}
        </StatusMessage>
      ) : null}
      {!isLoading && rows.length === 0 ? <EmptyState title="Chưa có nhân viên" /> : null}
      {rows.length > 0 ? (
        <Table>
          <thead>
            <tr>
              <th>Nhân viên</th>
              <th>Tên ca</th>
              <th>Mã ca</th>
              <th>Thời gian ca</th>
              <th>Effective date</th>
              <th>End date</th>
              <th>Trạng thái</th>
              {canManage ? <th>Thao tác</th> : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const assignment = row.assignment
              const shift = assignment ? shiftMap.get(assignment.shift_id) : undefined
              const canClose = assignment && row.status === 'current'
              const canEdit = assignment && row.status !== 'ended'
              const canDelete = assignment && row.status === 'upcoming'

              return (
                <tr key={row.employee.employee_id}>
                  <td>
                    <div className="table-person">
                      <strong>{row.employee.full_name}</strong>
                      <small>{row.employee.employee_code}</small>
                    </div>
                  </td>
                  <td>{shift?.name ?? '-'}</td>
                  <td>{shift?.code ?? '-'}</td>
                  <td>
                    {shift ? `${formatTime(shift.start_time)} - ${formatTime(shift.end_time)}` : '-'}
                  </td>
                  <td>{assignment ? formatDate(assignment.effective_date) : '-'}</td>
                  <td>{assignment ? (assignment.end_date ? formatDate(assignment.end_date) : 'Hiện tại') : '-'}</td>
                  <td>{getStatusBadge(row.status)}</td>
                  {canManage ? (
                    <td>
                      <div className="action-row">
                        {canClose ? (
                          <Button
                            isLoading={closeAssignment.isPending}
                            onClick={() => handleClose(assignment)}
                            size="sm"
                            variant="secondary"
                          >
                            Đóng ca
                          </Button>
                        ) : null}
                        {canEdit ? (
                          <Button
                            onClick={() => {
                              onEmployeeChange(assignment.employee_id)
                              onEditAssignment(assignment)
                            }}
                            size="sm"
                            variant="secondary"
                          >
                            Sửa
                          </Button>
                        ) : null}
                        {canDelete ? (
                          <Button
                            isLoading={deleteAssignment.isPending}
                            onClick={() => handleDelete(assignment)}
                            size="sm"
                            variant="danger"
                          >
                            Xóa
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  ) : null}
                </tr>
              )
            })}
          </tbody>
        </Table>
      ) : null}
    </section>
  )
}
