import { Badge } from '@/components/ui/Badge'
import type { EmployeeStatus } from '@/types/common.types'

type EmployeeStatusBadgeProps = {
  status: EmployeeStatus
}

const statusLabel: Record<EmployeeStatus, string> = {
  active: 'Đang làm',
  inactive: 'Tạm ngưng',
  resigned: 'Đã nghỉ',
}

export function EmployeeStatusBadge({ status }: EmployeeStatusBadgeProps) {
  const tone = status === 'active' ? 'green' : status === 'inactive' ? 'amber' : 'gray'

  return <Badge tone={tone}>{statusLabel[status]}</Badge>
}
