import { Badge } from '@/components/ui/Badge'
import { Table } from '@/components/ui/Table'
import type { Position } from '@/features/positions/types/position.types'
import { formatDateTime } from '@/lib/utils'

type PositionTableProps = {
  positions: Position[]
}

export function PositionTable({ positions }: PositionTableProps) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Tên chức vụ</th>
          <th>Mã</th>
          <th>Mô tả</th>
          <th>Trạng thái</th>
          <th>Cập nhật</th>
        </tr>
      </thead>
      <tbody>
        {positions.map((position) => (
          <tr key={position.position_id}>
            <td>
              <strong>{position.name}</strong>
            </td>
            <td>{position.code ?? '-'}</td>
            <td>{position.description ?? '-'}</td>
            <td>
              <Badge tone={position.is_active ? 'green' : 'gray'}>
                {position.is_active ? 'Hoạt động' : 'Tạm ngưng'}
              </Badge>
            </td>
            <td>{formatDateTime(position.updated_at)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
