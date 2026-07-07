import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { DepartmentForm } from '@/features/departments/components/DepartmentForm'
import { DepartmentTable } from '@/features/departments/components/DepartmentTable'
import { useDepartments } from '@/features/departments/hooks/useDepartments'
import { getApiErrorMessage } from '@/lib/utils'

export function DepartmentListPage() {
  const [search, setSearch] = useState('')
  const departmentsQuery = useDepartments(search)
  const departments = departmentsQuery.data ?? []

  return (
    <section className="page-grid">
      <div className="page-stack">
        <PageHeader
          description="Danh mục phòng ban từ /departments."
          eyebrow="Staff"
          title="Phòng ban"
        />
        <Input
          label="Tìm kiếm"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Tên hoặc mã phòng ban"
          value={search}
        />
        {departmentsQuery.isLoading ? <Loading /> : null}
        {departmentsQuery.isError ? (
          <StatusMessage tone="error">
            {getApiErrorMessage(departmentsQuery.error, 'Không thể tải danh sách phòng ban.')}
          </StatusMessage>
        ) : null}
        {!departmentsQuery.isLoading && !departmentsQuery.isError && departments.length === 0 ? (
          <EmptyState title="Chưa có phòng ban" />
        ) : null}
        {departments.length > 0 ? <DepartmentTable departments={departments} /> : null}
      </div>
      <aside className="side-panel">
        <h2>Tạo phòng ban</h2>
        <DepartmentForm />
      </aside>
    </section>
  )
}
