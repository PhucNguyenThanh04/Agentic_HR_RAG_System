import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import type { LeaveRequest, LeaveRequestStatus, LeaveTimeType } from '../types/leave.types'

type LeaveRequestTableProps = {
  requests: LeaveRequest[]
  employeeNames: Map<string, string>
  leaveTypeNames: Map<number, string>
  showEmployeeColumn?: boolean
  onCancel?: (requestId: string) => void
  onReview?: (request: LeaveRequest) => void
  isCancelling?: boolean
}

const statusTones: Record<LeaveRequestStatus, 'amber' | 'green' | 'red' | 'gray'> = {
  pending: 'amber',
  approved: 'green',
  rejected: 'red',
  cancelled: 'gray',
}

const statusLabels: Record<LeaveRequestStatus, string> = {
  pending: 'Chờ duyệt',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  cancelled: 'Đã hủy',
}

const timeTypeLabels: Record<LeaveTimeType, string> = {
  full_day: 'Cả ngày',
  morning: 'Buổi sáng',
  afternoon: 'Buổi chiều',
  custom: 'Tự chọn',
}

export function LeaveRequestTable({
  requests,
  employeeNames,
  leaveTypeNames,
  showEmployeeColumn = false,
  onCancel,
  onReview,
  isCancelling = false,
}: LeaveRequestTableProps) {
  return (
    <div className="table-wrapper">
      <table className="table">
        <thead>
          <tr>
            {showEmployeeColumn ? <th>Nhân viên</th> : null}
            <th>Loại phép</th>
            <th>Thời gian</th>
            <th>Hình thức</th>
            <th>Số ngày</th>
            <th>Lý do xin nghỉ</th>
            <th>Trạng thái</th>
            {onCancel || onReview ? <th style={{ textAlign: 'right' }}>Thao tác</th> : null}
          </tr>
        </thead>
        <tbody>
          {requests.map((request) => {
            const employeeName = employeeNames.get(request.employee_id) || 'Không xác định'
            const leaveTypeName = leaveTypeNames.get(request.leave_type_id) || 'Không xác định'

            return (
              <tr key={request.request_id}>
                {showEmployeeColumn ? (
                  <td>
                    <strong>{employeeName}</strong>
                  </td>
                ) : null}
                <td>{leaveTypeName}</td>
                <td>
                  <span style={{ whiteSpace: 'nowrap' }}>
                    {request.start_date} {request.end_date !== request.start_date ? `đến ${request.end_date}` : ''}
                  </span>
                </td>
                <td>{timeTypeLabels[request.time_type] || request.time_type}</td>
                <td>
                  <strong>{request.total_days}</strong> ngày
                </td>
                <td>
                  <span title={request.reason || undefined} style={{ display: 'inline-block', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {request.reason || '-'}
                  </span>
                </td>
                <td>
                  <Badge tone={statusTones[request.status]}>{statusLabels[request.status]}</Badge>
                  {request.status === 'rejected' && request.rejection_reason ? (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      Lý do: {request.rejection_reason}
                    </div>
                  ) : null}
                </td>
                {onCancel || onReview ? (
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      {onReview && request.status === 'pending' ? (
                        <Button onClick={() => onReview(request)} size="sm" variant="primary">
                          Duyệt
                        </Button>
                      ) : null}
                      {onCancel && request.status === 'pending' ? (
                        <Button
                          disabled={isCancelling}
                          onClick={() => onCancel(request.request_id)}
                          size="sm"
                          variant="secondary"
                        >
                          Hủy đơn
                        </Button>
                      ) : null}
                    </div>
                  </td>
                ) : null}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
