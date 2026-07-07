import { Badge } from '@/components/ui/Badge'
import type { FaceProfileStatus } from '@/types/common.types'

type FaceProfileStatusBadgeProps = {
  status: FaceProfileStatus
}

const labelByStatus: Record<FaceProfileStatus, string> = {
  active: 'Active',
  failed: 'Failed',
  pending: 'Pending',
  revoked: 'Revoked',
}

export function FaceProfileStatusBadge({ status }: FaceProfileStatusBadgeProps) {
  const tone =
    status === 'active' ? 'green' : status === 'pending' ? 'amber' : status === 'failed' ? 'red' : 'gray'

  return <Badge tone={tone}>{labelByStatus[status]}</Badge>
}
