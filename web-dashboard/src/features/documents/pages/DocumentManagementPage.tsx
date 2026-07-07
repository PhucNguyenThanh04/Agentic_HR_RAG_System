import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Loading } from '@/components/ui/Loading'
import { Pagination } from '@/components/ui/Pagination'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { DocumentDetailPanel } from '@/features/documents/components/DocumentDetailPanel'
import { DocumentTable } from '@/features/documents/components/DocumentTable'
import { DocumentUploadForm } from '@/features/documents/components/DocumentUploadForm'
import { useDeleteDocument } from '@/features/documents/hooks/useDeleteDocument'
import { useDocuments } from '@/features/documents/hooks/useDocuments'
import type { DocumentStatus } from '@/features/documents/types/document.types'
import { getApiErrorMessage } from '@/lib/utils'
import type { RoleName } from '@/types/common.types'

const PAGE_SIZE = 10

export function DocumentManagementPage() {
  const [allowedRole, setAllowedRole] = useState<RoleName | ''>('')
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null)
  const [fileType, setFileType] = useState('')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [status, setStatus] = useState<DocumentStatus | ''>('')
  const documentsQuery = useDocuments({
    allowed_role: allowedRole || undefined,
    file_type: fileType || undefined,
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    status: status || undefined,
  })
  const deleteDocument = useDeleteDocument()
  const documents = documentsQuery.data?.items ?? []

  const handleDelete = (documentId: string) => {
    const confirmed = window.confirm('Xóa tài liệu này khỏi database và vector store?')
    if (!confirmed) {
      return
    }

    setDeletingDocumentId(documentId)
    deleteDocument.mutate(documentId, {
      onSettled: () => setDeletingDocumentId(null),
      onSuccess: () => {
        if (selectedDocumentId === documentId) {
          setSelectedDocumentId(null)
        }
      },
    })
  }

  return (
    <section className="page-grid page-grid--wide">
      <div className="page-stack">
        <PageHeader
          description="Upload tài liệu để ingest vào RAG vector store và quản lý metadata /documents."
          eyebrow="Knowledge Base"
          title="Tài liệu vector store"
        />
        <div className="toolbar toolbar--documents">
          <Input
            label="Tìm kiếm"
            onChange={(event) => {
              setSearch(event.target.value)
              setPage(1)
            }}
            placeholder="Tiêu đề hoặc tên file"
            value={search}
          />
          <Select
            label="Role"
            onChange={(event) => {
              setAllowedRole(event.target.value as RoleName | '')
              setPage(1)
            }}
            value={allowedRole}
          >
            <option value="">Tất cả</option>
            <option value="admin">Admin</option>
            <option value="hr">HR</option>
            <option value="manager">Manager</option>
            <option value="employee">Employee</option>
          </Select>
          <Select
            label="Trạng thái"
            onChange={(event) => {
              setStatus(event.target.value as DocumentStatus | '')
              setPage(1)
            }}
            value={status}
          >
            <option value="">Tất cả</option>
            <option value="processing">Đang xử lý</option>
            <option value="ready">Sẵn sàng</option>
            <option value="failed">Lỗi</option>
          </Select>
          <Select
            label="Loại file"
            onChange={(event) => {
              setFileType(event.target.value)
              setPage(1)
            }}
            value={fileType}
          >
            <option value="">Tất cả</option>
            <option value="pdf">PDF</option>
            <option value="txt">TXT</option>
            <option value="docx">DOCX</option>
          </Select>
        </div>
        {documentsQuery.isLoading ? <Loading /> : null}
        {documentsQuery.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(documentsQuery.error, 'Không thể tải danh sách tài liệu.')}
          </StatusMessage>
        ) : null}
        {deleteDocument.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(deleteDocument.error, 'Không thể xóa tài liệu.')}
          </StatusMessage>
        ) : null}
        {!documentsQuery.isLoading && !documentsQuery.isError && documents.length === 0 ? (
          <EmptyState
            description="Upload file PDF, TXT hoặc DOCX để bắt đầu tạo knowledge base."
            title="Chưa có tài liệu"
          />
        ) : null}
        {documents.length > 0 ? (
          <>
            <DocumentTable
              deletingDocumentId={deletingDocumentId}
              documents={documents}
              onDelete={handleDelete}
              onSelect={setSelectedDocumentId}
              selectedDocumentId={selectedDocumentId}
            />
            <Pagination
              currentPage={documentsQuery.data?.page ?? page}
              isFetching={documentsQuery.isFetching}
              onPageChange={setPage}
              pageSize={documentsQuery.data?.page_size ?? PAGE_SIZE}
              total={documentsQuery.data?.total ?? 0}
            />
          </>
        ) : null}
      </div>
      <aside className="side-panel side-panel--sticky">
        <h2>Thêm tài liệu</h2>
        <DocumentUploadForm />
        <div className="panel-divider" />
        <h2>Chi tiết</h2>
        <DocumentDetailPanel documentId={selectedDocumentId} />
      </aside>
    </section>
  )
}
