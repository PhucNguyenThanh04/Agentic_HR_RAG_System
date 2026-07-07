import { useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import type { Employee } from '@/features/employees/types/employee.types'
import { useChangeShift } from '@/features/shifts/hooks/useChangeShift'
import { useCurrentShift } from '@/features/shifts/hooks/useCurrentShift'
import type { WorkShift } from '@/features/shifts/types/shift.types'
import { getApiErrorMessage } from '@/lib/utils'

type ChangeShiftModalProps = {
  employees: Employee[]
  isOpen: boolean
  onClose: () => void
  selectedEmployeeId: string
  shifts: WorkShift[]
}

type ChangeShiftValues = {
  effective_date: string
  employee_id: string
  new_shift_id: string
  reason: string
}

function getToday(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function getInitialValues(employeeId: string, shifts: WorkShift[]): ChangeShiftValues {
  return {
    effective_date: getToday(),
    employee_id: employeeId,
    new_shift_id: shifts[0] ? String(shifts[0].shift_id) : '',
    reason: '',
  }
}

function formatTime(value?: string): string {
  return value ? value.slice(0, 5) : '-'
}

export function ChangeShiftModal({
  employees,
  isOpen,
  onClose,
  selectedEmployeeId,
  shifts,
}: ChangeShiftModalProps) {
  const activeShifts = useMemo(() => shifts.filter((shift) => shift.is_active), [shifts])
  const [values, setValues] = useState<ChangeShiftValues>(() =>
    getInitialValues(selectedEmployeeId, activeShifts),
  )
  const changeShift = useChangeShift()
  const currentShiftQuery = useCurrentShift(values.employee_id, values.effective_date, isOpen)

  if (!isOpen) {
    return null
  }

  const handleChange =
    (fieldName: keyof ChangeShiftValues) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setValues((currentValues) => ({
        ...currentValues,
        [fieldName]: event.target.value,
      }))
    }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!values.employee_id || !values.new_shift_id || !values.effective_date) {
      return
    }

    changeShift.mutate(
      {
        employeeId: values.employee_id,
        payload: {
          effective_date: values.effective_date,
          new_shift_id: Number(values.new_shift_id),
          reason: values.reason || null,
        },
      },
      {
        onSuccess: () => {
          onClose()
          setValues(getInitialValues(values.employee_id, activeShifts))
        },
      },
    )
  }

  const currentShift = currentShiftQuery.data?.shift

  return (
    <div aria-modal="true" className="modal-backdrop" role="dialog">
      <section className="modal">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Change shift</p>
            <h2>Đổi ca</h2>
          </div>
          <Button onClick={onClose} size="sm" variant="secondary">
            Đóng
          </Button>
        </div>
        <form className="resource-form" onSubmit={handleSubmit}>
          <Select
            label="Nhân viên"
            name="employee_id"
            onChange={handleChange('employee_id')}
            value={values.employee_id}
          >
            <option value="">Chọn nhân viên</option>
            {employees.map((employee) => (
              <option key={employee.employee_id} value={employee.employee_id}>
                {employee.employee_code} - {employee.full_name}
              </option>
            ))}
          </Select>
          {currentShiftQuery.isLoading ? <LoadingInline /> : null}
          {currentShift ? (
            <StatusMessage tone="info">
              Ca hiện tại: {currentShift.name} {currentShift.code ? `(${currentShift.code})` : ''},{' '}
              {formatTime(currentShift.start_time)} - {formatTime(currentShift.end_time)}
            </StatusMessage>
          ) : null}
          {currentShiftQuery.isError ? (
            <StatusMessage tone="warning">Chưa tìm thấy ca hiện tại cho ngày áp dụng.</StatusMessage>
          ) : null}
          <Select
            label="Ca mới"
            name="new_shift_id"
            onChange={handleChange('new_shift_id')}
            value={values.new_shift_id}
          >
            <option value="">Chọn ca mới</option>
            {activeShifts.map((shift) => (
              <option key={shift.shift_id} value={shift.shift_id}>
                {shift.name} {shift.code ? `(${shift.code})` : ''}
              </option>
            ))}
          </Select>
          <Input
            label="Ngày áp dụng"
            name="effective_date"
            onChange={handleChange('effective_date')}
            type="date"
            value={values.effective_date}
          />
          <Input
            label="Lý do"
            name="reason"
            onChange={handleChange('reason')}
            placeholder="Không bắt buộc"
            value={values.reason}
          />
          {changeShift.isError ? (
            <StatusMessage tone="error">
              {getApiErrorMessage(changeShift.error, 'Không thể đổi ca.')}
            </StatusMessage>
          ) : null}
          <Button
            disabled={!values.employee_id || !values.new_shift_id || !values.effective_date}
            isLoading={changeShift.isPending}
            type="submit"
          >
            Đổi ca
          </Button>
        </form>
      </section>
    </div>
  )
}

function LoadingInline() {
  return <StatusMessage tone="info">Đang tải ca hiện tại...</StatusMessage>
}
