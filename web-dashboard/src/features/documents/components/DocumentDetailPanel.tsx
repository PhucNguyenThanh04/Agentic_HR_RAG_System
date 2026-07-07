import { Button } from '@/components/ui/Button'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { DocumentStatusBadge } from '@/features/documents/components/DocumentStatusBadge'
import { useDocumentDetail } from '@/features/documents/hooks/useDocumentDetail'
import { formatDateTime, getApiErrorMessage } from '@/lib/utils'

type DocumentDetailPanelProps = {
  documentId: string | null
}

export function DocumentDetailPanel({ documentId }: DocumentDetailPanelProps) {
  const detailQuery = useDocumentDetail(documentId)
  const document = detailQuery.data

  if (!documentId) {
    return <p className="muted-text">Chọn một tài liệu để xem metadata trong vector store.</p>
  }

  if (detailQuery.isLoading) {
    return <Loading label="Đang tải chi tiết tài liệu" />
  }

  if (detailQuery.isError) {
    return (
      <StatusMessage tone="error">
        {getApiErrorMessage(detailQuery.error, 'Không thể tải chi tiết tài liệu.')}
      </StatusMessage>
    )
  }

  if (!document) {
    return null
  }

  return (
    <div className="detail-list">
      <div>
        <span>Trạng thái</span>
        <DocumentStatusBadge status={document.status} />
      </div>
      <div>
        <span>ID</span>
        <strong className="mono-cell">{document.id}</strong>
      </div>
      <div>
        <span>File</span>
        <strong>{document.file_name}</strong>
      </div>
      <div>
        <span>Loại</span>
        <strong>{document.file_type.toUpperCase()}</strong>
      </div>
      <div>
        <span>Collection</span>
        <strong className="mono-cell">{document.qdrant_collection}</strong>
      </div>
      <div>
        <span>Chunks</span>
        <strong>{document.chunk_count}</strong>
      </div>
      <div>
        <span>Role</span>
        <strong>{document.allowed_roles.join(', ')}</strong>
      </div>
      <div>
        <span>Ngày tạo</span>
        <strong>{formatDateTime(document.created_at)}</strong>
      </div>
      <Button
        onClick={() => window.open(document.file_url, '_blank', 'noopener,noreferrer')}
        variant="secondary"
      >
        Mở file
      </Button>
    </div>
  )
}
