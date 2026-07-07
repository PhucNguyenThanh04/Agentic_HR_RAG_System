import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import type { WorkShift } from '@/features/shifts/types/shift.types'
import { formatDateTime } from '@/lib/utils'

type WorkShiftTableProps = {
  canManage: boolean
  isToggling?: boolean
  onEdit?: (shift: WorkShift) => void
  onToggle?: (shift: WorkShift) => void
  shifts: WorkShift[]
}

function formatTime(value: string): string {
  return value.slice(0, 5)
}

function formatRequiredMinutes(value: number | null): string {
  return value === null ? '-' : `${value} phút`
}

export function WorkShiftTable({
  canManage,
  isToggling = false,
  onEdit,
  onToggle,
  shifts,
}: WorkShiftTableProps) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Ca làm việc</th>
          <th>Thời gian</th>
          <th>Ngưỡng</th>
          <th>Phút yêu cầu</th>
          <th>Trạng thái</th>
          <th>Cập nhật</th>
          {canManage ? <th>Thao tác</th> : null}
        </tr>
      </thead>
      <tbody>
        {shifts.map((shift) => (
          <tr key={shift.shift_id}>
            <td>
              <div className="table-person">
                <strong>{shift.name}</strong>
                <small>{shift.code ?? `#${shift.shift_id}`}</small>
              </div>
            </td>
            <td>
              <div className="table-person">
                <span>
                  {formatTime(shift.start_time)} - {formatTime(shift.end_time)}
                </span>
                <small>
                  {shift.is_overnight ? <Badge tone="blue">Qua đêm</Badge> : 'Trong ngày'}
                </small>
              </div>
            </td>
            <td>
              <div className="table-person">
                <span>Trễ: {shift.late_threshold_minutes} phút</span>
                <small>Về sớm: {shift.early_leave_threshold_minutes} phút</small>
              </div>
            </td>
            <td>{formatRequiredMinutes(shift.required_work_minutes)}</td>
            <td>
              <Badge tone={shift.is_active ? 'green' : 'gray'}>
                {shift.is_active ? 'Hoạt động' : 'Ngừng'}
              </Badge>
            </td>
            <td>{formatDateTime(shift.updated_at)}</td>
            {canManage ? (
              <td>
                <div className="action-row">
                  <Button onClick={() => onEdit?.(shift)} size="sm" variant="secondary">
                    Sửa
                  </Button>
                  <Button
                    disabled={isToggling}
                    onClick={() => onToggle?.(shift)}
                    size="sm"
                    variant={shift.is_active ? 'danger' : 'primary'}
                  >
                    {shift.is_active ? 'Tắt' : 'Bật'}
                  </Button>
                </div>
              </td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
