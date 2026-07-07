import { Badge } from '@/components/ui/Badge'
import type { DocumentStatus } from '@/features/documents/types/document.types'

type DocumentStatusBadgeProps = {
  status: DocumentStatus
}

const statusLabels: Record<DocumentStatus, string> = {
  failed: 'Lỗi',
  processing: 'Đang xử lý',
  ready: 'Sẵn sàng',
}

export function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  const tone = status === 'ready' ? 'green' : status === 'failed' ? 'red' : 'amber'

  return <Badge tone={tone}>{statusLabels[status]}</Badge>
}
