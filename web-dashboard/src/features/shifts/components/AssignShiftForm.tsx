import { useMemo, useState, type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import type { Employee } from '@/features/employees/types/employee.types'
import { useCreateShiftAssignment } from '@/features/shifts/hooks/useCreateShiftAssignment'
import { useCurrentShift } from '@/features/shifts/hooks/useCurrentShift'
import { useUpdateShiftAssignment } from '@/features/shifts/hooks/useUpdateShiftAssignment'
import { shiftAssignmentSchema } from '@/features/shifts/schemas/shift.schema'
import type {
  CreateShiftAssignmentPayload,
  EmployeeShiftAssignment,
  WorkShift,
} from '@/features/shifts/types/shift.types'
import { getApiErrorMessage } from '@/lib/utils'

type AssignShiftFormProps = {
  employees: Employee[]
  onCancelEdit?: () => void
  onEmployeeChange?: (employeeId: string) => void
  selectedAssignment?: EmployeeShiftAssignment | null
  selectedEmployeeId: string
  shifts: WorkShift[]
}

type AssignShiftValues = {
  effective_date: string
  employee_id: string
  end_date: string
  shift_id: string
}

type AssignShiftErrors = Partial<Record<keyof AssignShiftValues, string>>

function getToday(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function getDefaultValues(
  employeeId: string,
  shifts: WorkShift[],
  selectedAssignment?: EmployeeShiftAssignment | null,
): AssignShiftValues {
  if (selectedAssignment) {
    return {
      effective_date: selectedAssignment.effective_date,
      employee_id: selectedAssignment.employee_id,
      end_date: selectedAssignment.end_date ?? '',
      shift_id: String(selectedAssignment.shift_id),
    }
  }

  return {
    effective_date: getToday(),
    employee_id: employeeId,
    end_date: '',
    shift_id: shifts[0] ? String(shifts[0].shift_id) : '',
  }
}

function getValidationErrors(values: AssignShiftValues): AssignShiftErrors {
  const result = shiftAssignmentSchema.safeParse(values)

  if (result.success) {
    return {}
  }

  return result.error.issues.reduce<AssignShiftErrors>((accumulator, issue) => {
    const fieldName = issue.path[0]

    if (typeof fieldName === 'string' && fieldName in values && !accumulator[fieldName as keyof AssignShiftValues]) {
      accumulator[fieldName as keyof AssignShiftValues] = issue.message
    }

    return accumulator
  }, {})
}

function toPayload(values: AssignShiftValues): CreateShiftAssignmentPayload {
  return {
    effective_date: values.effective_date,
    end_date: values.end_date || null,
    shift_id: Number(values.shift_id),
  }
}

export function AssignShiftForm({
  employees,
  onCancelEdit,
  onEmployeeChange,
  selectedAssignment,
  selectedEmployeeId,
  shifts,
}: AssignShiftFormProps) {
  const isEditing = Boolean(selectedAssignment)
  const [errors, setErrors] = useState<AssignShiftErrors>({})
  const [values, setValues] = useState<AssignShiftValues>(() =>
    getDefaultValues(selectedEmployeeId, shifts, selectedAssignment),
  )

  const createAssignment = useCreateShiftAssignment()
  const updateAssignment = useUpdateShiftAssignment(values.employee_id)
  const currentShiftQuery = useCurrentShift(values.employee_id, undefined, Boolean(values.employee_id))
  const showCurrentShiftWarning = !isEditing && Boolean(currentShiftQuery.data)
  const shiftOptions = useMemo(
    () => shifts.filter((shift) => shift.is_active),
    [shifts],
  )

  const setFieldValue = (fieldName: keyof AssignShiftValues, value: string) => {
    setValues((currentValues) => ({
      ...currentValues,
      [fieldName]: value,
    }))
    setErrors((currentErrors) => ({
      ...currentErrors,
      [fieldName]: undefined,
    }))
  }

  const handleChange =
    (fieldName: keyof AssignShiftValues) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const nextValue = event.target.value
      setFieldValue(fieldName, nextValue)

      if (fieldName === 'employee_id') {
        onEmployeeChange?.(nextValue)
      }
    }

  const resetForm = (employeeId = values.employee_id) => {
    setErrors({})
    setValues(getDefaultValues(employeeId, shifts))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const validationErrors = getValidationErrors(values)

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      return
    }

    if (selectedAssignment) {
      updateAssignment.mutate(
        {
          assignmentId: selectedAssignment.assignment_id,
          payload: toPayload(values),
        },
        {
          onSuccess: () => {
            onCancelEdit?.()
            resetForm(values.employee_id)
          },
        },
      )
      return
    }

    createAssignment.mutate(
      {
        employeeId: values.employee_id,
        payload: toPayload(values),
      },
      {
        onSuccess: () => resetForm(values.employee_id),
      },
    )
  }

  const mutationError = createAssignment.error ?? updateAssignment.error
  const isPending = createAssignment.isPending || updateAssignment.isPending

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      <Select
        disabled={isEditing}
        error={errors.employee_id}
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
      <Select
        error={errors.shift_id}
        label="Ca đang active"
        name="shift_id"
        onChange={handleChange('shift_id')}
        value={values.shift_id}
      >
        <option value="">Chọn ca</option>
        {shiftOptions.map((shift) => (
          <option key={shift.shift_id} value={shift.shift_id}>
            {shift.name} {shift.code ? `(${shift.code})` : ''}
          </option>
        ))}
      </Select>
      <div className="form-grid">
        <Input
          error={errors.effective_date}
          label="Effective date"
          name="effective_date"
          onChange={handleChange('effective_date')}
          type="date"
          value={values.effective_date}
        />
        <Input
          error={errors.end_date}
          label="End date"
          name="end_date"
          onChange={handleChange('end_date')}
          type="date"
          value={values.end_date}
        />
      </div>
      {showCurrentShiftWarning ? (
        <StatusMessage tone="warning">
          Nhân viên này đã có ca đang hiệu lực. Nếu muốn chuyển ca, hãy dùng chức năng Đổi ca.
        </StatusMessage>
      ) : null}
      {mutationError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(mutationError, 'Không thể lưu phân công ca.')}
        </StatusMessage>
      ) : null}
      <div className="action-row">
        <Button
          disabled={employees.length === 0 || shiftOptions.length === 0}
          isLoading={isPending}
          type="submit"
        >
          {isEditing ? 'Cập nhật phân công' : 'Gán ca'}
        </Button>
        {isEditing ? (
          <Button onClick={onCancelEdit} type="button" variant="secondary">
            Hủy sửa
          </Button>
        ) : null}
      </div>
    </form>
  )
}
