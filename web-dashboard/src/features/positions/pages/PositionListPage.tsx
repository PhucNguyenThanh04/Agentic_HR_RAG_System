import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { PositionForm } from '@/features/positions/components/PositionForm'
import { PositionTable } from '@/features/positions/components/PositionTable'
import { usePositions } from '@/features/positions/hooks/usePositions'
import { getApiErrorMessage } from '@/lib/utils'

export function PositionListPage() {
  const [search, setSearch] = useState('')
  const positionsQuery = usePositions(search)
  const positions = positionsQuery.data ?? []

  return (
    <section className="page-grid">
      <div className="page-stack">
        <PageHeader
          description="Danh mục chức vụ từ /positions."
          eyebrow="Staff"
          title="Chức vụ"
        />
        <Input
          label="Tìm kiếm"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tên hoặc mã chức vụ"
          value={search}
        />
        {positionsQuery.isLoading ? <Loading /> : null}
        {positionsQuery.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(positionsQuery.error, 'Không thể tải danh sách chức vụ.')}
          </StatusMessage>
        ) : null}
        {!positionsQuery.isLoading && !positionsQuery.isError && positions.length === 0 ? (
          <EmptyState title="Chưa có chức vụ" />
        ) : null}
        {positions.length > 0 ? <PositionTable positions={positions} /> : null}
      </div>
      <aside className="side-panel">
        <h2>Tạo chức vụ</h2>
        <PositionForm />
      </aside>
    </section>
  )
}
