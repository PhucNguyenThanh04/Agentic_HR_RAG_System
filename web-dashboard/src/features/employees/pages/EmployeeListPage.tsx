import { useMemo, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { Input } from '@/components/ui/Input'
import { Loading } from '@/components/ui/Loading'
import { Pagination } from '@/components/ui/Pagination'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useDepartments } from '@/features/departments/hooks/useDepartments'
import { useEmployees } from '@/features/employees/hooks/useEmployees'
import { EmployeeTable } from '@/features/employees/components/EmployeeTable'
import { usePositions } from '@/features/positions/hooks/usePositions'
import { getApiErrorMessage } from '@/lib/utils'
import type { EmployeeStatus } from '@/types/common.types'

const PAGE_SIZE = 12

export function EmployeeListPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<EmployeeStatus | ''>('')
  const employeesQuery = useEmployees({
    page,
    page_size: PAGE_SIZE,
    search: search || undefined,
    status: status || undefined,
  })
  const departmentsQuery = useDepartments()
  const positionsQuery = usePositions()

  const departmentNames = useMemo(
    () => new Map((departmentsQuery.data ?? []).map((department) => [department.department_id, department.name])),
    [departmentsQuery.data],
  )
  const positionNames = useMemo(
    () => new Map((positionsQuery.data ?? []).map((position) => [position.position_id, position.name])),
    [positionsQuery.data],
  )

  const employees = employeesQuery.data?.items ?? []

  return (
    <section className="page-stack">
      <PageHeader
        description="Tra cứu nhân sự theo contract /employees của API service."
        eyebrow="Staff"
        title="Nhân viên"
      />
      <div className="toolbar">
        <Input
          label="Tìm kiếm"
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
          }}
          placeholder="Tên hoặc mã nhân viên"
          value={search}
        />
        <Select
          label="Trạng thái"
          onChange={(event) => {
            setStatus(event.target.value as EmployeeStatus | '')
            setPage(1)
          }}
          value={status}
        >
          <option value="">Tất cả</option>
          <option value="active">Đang làm</option>
          <option value="inactive">Tạm ngưng</option>
          <option value="resigned">Đã nghỉ</option>
        </Select>
      </div>
      {employeesQuery.isLoading ? <Loading /> : null}
      {employeesQuery.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(employeesQuery.error, 'Không thể tải danh sách nhân viên.')}
        </StatusMessage>
      ) : null}
      {!employeesQuery.isLoading && !employeesQuery.isError && employees.length === 0 ? (
        <EmptyState
          description="Thử đổi bộ lọc hoặc tạo nhân viên qua màn onboarding."
          title="Chưa có nhân viên phù hợp"
        />
      ) : null}
      {employees.length > 0 ? (
        <>
          <EmployeeTable
            departmentNames={departmentNames}
            employees={employees}
            positionNames={positionNames}
          />
          <Pagination
            currentPage={employeesQuery.data?.page ?? page}
            isFetching={employeesQuery.isFetching}
            onPageChange={setPage}
            pageSize={employeesQuery.data?.page_size ?? PAGE_SIZE}
            total={employeesQuery.data?.total ?? 0}
          />
        </>
      ) : null}
    </section>
  )
}
