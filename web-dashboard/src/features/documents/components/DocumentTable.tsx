import { Button } from '@/components/ui/Button'
import { Table } from '@/components/ui/Table'
import { DocumentStatusBadge } from '@/features/documents/components/DocumentStatusBadge'
import type { DocumentItem } from '@/features/documents/types/document.types'
import { formatDateTime } from '@/lib/utils'

type DocumentTableProps = {
  deletingDocumentId?: string | null
  documents: DocumentItem[]
  onDelete: (documentId: string) => void
  onSelect: (documentId: string) => void
  selectedDocumentId?: string | null
}

export function DocumentTable({
  deletingDocumentId,
  documents,
  onDelete,
  onSelect,
  selectedDocumentId,
}: DocumentTableProps) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Tài liệu</th>
          <th>Role</th>
          <th>Vector</th>
          <th>Trạng thái</th>
          <th>Cập nhật</th>
          <th>Thao tác</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((document) => (
          <tr key={document.id}>
            <td>
              <div className="table-person">
                <strong>{document.title}</strong>
                <small>{document.file_name}</small>
              </div>
            </td>
            <td>{document.allowed_roles.join(', ')}</td>
            <td>
              <span className="mono-cell">
                {document.qdrant_collection} / {document.chunk_count} chunks
              </span>
            </td>
            <td>
              <DocumentStatusBadge status={document.status} />
            </td>
            <td>{formatDateTime(document.updated_at)}</td>
            <td>
              <div className="table-actions">
                <Button
                  onClick={() => onSelect(document.id)}
                  size="sm"
                  variant={selectedDocumentId === document.id ? 'primary' : 'secondary'}
                >
                  Chi tiết
                </Button>
                <Button
                  isLoading={deletingDocumentId === document.id}
                  onClick={() => onDelete(document.id)}
                  size="sm"
                  variant="danger"
                >
                  Xóa
                </Button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
