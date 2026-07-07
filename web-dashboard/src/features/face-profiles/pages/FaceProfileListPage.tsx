import { useMemo, useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { Loading } from '@/components/ui/Loading'
import { Pagination } from '@/components/ui/Pagination'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { FaceProfileTable } from '@/features/face-profiles/components/FaceProfileTable'
import { useFaceProfiles } from '@/features/face-profiles/hooks/useFaceProfiles'
import { useEmployees } from '@/features/employees/hooks/useEmployees'
import { getApiErrorMessage } from '@/lib/utils'
import type { FaceProfileStatus } from '@/types/common.types'

const PAGE_SIZE = 12

export function FaceProfileListPage() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<FaceProfileStatus | ''>('')
  const profilesQuery = useFaceProfiles({
    page,
    page_size: PAGE_SIZE,
    status: status || undefined,
  })
  const profiles = profilesQuery.data?.items ?? []

  const employeesQuery = useEmployees({ page: 1, page_size: 200 })
  const employees = employeesQuery.data?.items
  const employeeNames = useMemo(
    () => new Map((employees ?? []).map((emp) => [emp.employee_id, emp.full_name])),
    [employees],
  )

  return (
    <section className="page-stack">
      <PageHeader
        description="Theo dõi trạng thái vector nhận diện khuôn mặt từ /face-profiles."
        eyebrow="AI identity"
        title="Face profiles"
      />
      <div className="toolbar toolbar--compact">
        <Select
          label="Trạng thái"
          onChange={(event) => {
            setStatus(event.target.value as FaceProfileStatus | '')
            setPage(1)
          }}
          value={status}
        >
          <option value="">Tất cả</option>
          <option value="pending">Pending</option>
          <option value="active">Active</option>
          <option value="revoked">Revoked</option>
          <option value="failed">Failed</option>
        </Select>
      </div>
      {profilesQuery.isLoading || employeesQuery.isLoading ? <Loading /> : null}
      {profilesQuery.isError || employeesQuery.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(
            profilesQuery.error || employeesQuery.error,
            'Không thể tải danh sách face profiles.'
          )}
        </StatusMessage>
      ) : null}
      {!profilesQuery.isLoading && !profilesQuery.isError && profiles.length === 0 ? (
        <EmptyState
          description="Face profile sẽ xuất hiện sau khi onboarding có ảnh hợp lệ và commit thành công."
          title="Chưa có face profile phù hợp"
        />
      ) : null}
      {profiles.length > 0 ? (
        <>
          <FaceProfileTable employeeNames={employeeNames} profiles={profiles} />
          <Pagination
            currentPage={profilesQuery.data?.page ?? page}
            isFetching={profilesQuery.isFetching}
            onPageChange={setPage}
            pageSize={profilesQuery.data?.page_size ?? PAGE_SIZE}
            total={profilesQuery.data?.total ?? 0}
          />
        </>
      ) : null}
    </section>
  )
}
