import { Table } from '@/components/ui/Table'
import { EmployeeStatusBadge } from '@/features/employees/components/EmployeeStatusBadge'
import type { Employee } from '@/features/employees/types/employee.types'
import { formatDate } from '@/lib/utils'

type EmployeeTableProps = {
  departmentNames: Map<number, string>
  employees: Employee[]
  positionNames: Map<number, string>
}

function getNameById(names: Map<number, string>, id: number | null): string {
  return id ? names.get(id) ?? `#${id}` : '-'
}

export function EmployeeTable({ departmentNames, employees, positionNames }: EmployeeTableProps) {
  return (
    <Table>
      <thead>
        <tr>
          <th>Mã NV</th>
          <th>Họ tên</th>
          <th>Phòng ban</th>
          <th>Chức vụ</th>
          <th>Ngày vào</th>
          <th>Trạng thái</th>
        </tr>
      </thead>
      <tbody>
        {employees.map((employee) => (
          <tr key={employee.employee_id}>
            <td>
              <strong>{employee.employee_code}</strong>
            </td>
            <td>
              <div className="table-person">
                <span>{employee.full_name}</span>
                <small>{employee.phone ?? 'Chưa có số điện thoại'}</small>
              </div>
            </td>
            <td>{getNameById(departmentNames, employee.department_id)}</td>
            <td>{getNameById(positionNames, employee.position_id)}</td>
            <td>{formatDate(employee.hire_date)}</td>
            <td>
              <EmployeeStatusBadge status={employee.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
