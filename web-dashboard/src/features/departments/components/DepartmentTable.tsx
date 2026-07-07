import { Badge } from '@/components/ui/Badge'
import { Table } from '@/components/ui/Table'
import type { Department } from '@/features/departments/types/department.types'
import { formatDateTime } from '@/lib/utils'

type DepartmentTableProps = {
  departments: Department[]
}

export function DepartmentTable({ departments }: DepartmentTableProps) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Tên phòng ban</th>
          <th>Mã</th>
          <th>Mô tả</th>
          <th>Trạng thái</th>
          <th>Cập nhật</th>
        </tr>
      </thead>
      <tbody>
        {departments.map((department) => (
          <tr key={department.department_id}>
            <td>
              <strong>{department.name}</strong>
            </td>
            <td>{department.code ?? '-'}</td>
            <td>{department.description ?? '-'}</td>
            <td>
              <Badge tone={department.is_active ? 'green' : 'gray'}>
                {department.is_active ? 'Hoạt động' : 'Tạm ngưng'}
              </Badge>
            </td>
            <td>{formatDateTime(department.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
