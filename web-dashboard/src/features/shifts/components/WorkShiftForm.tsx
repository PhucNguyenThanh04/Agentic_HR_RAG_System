import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useCreateWorkShift } from '@/features/shifts/hooks/useCreateWorkShift'
import { useUpdateWorkShift } from '@/features/shifts/hooks/useUpdateWorkShift'
import {
  workShiftSchema,
  type WorkShiftFormValues,
} from '@/features/shifts/schemas/shift.schema'
import type { CreateWorkShiftPayload, WorkShift } from '@/features/shifts/types/shift.types'
import { getApiErrorMessage } from '@/lib/utils'

type WorkShiftFormProps = {
  onCancelEdit?: () => void
  selectedShift?: WorkShift | null
}

const defaultValues: WorkShiftFormValues = {
  code: '',
  early_leave_threshold_minutes: '0',
  end_time: '17:00',
  is_active: true,
  is_overnight: false,
  late_threshold_minutes: '0',
  name: '',
  required_work_minutes: '',
  start_time: '08:00',
}

type WorkShiftFormErrors = Partial<Record<keyof WorkShiftFormValues, string>>

function toTimeInput(value: string): string {
  return value.slice(0, 5)
}

function toApiTime(value: string): string {
  return value.length === 5 ? `${value}:00` : value
}

function toOptionalNumber(value: string): number | null {
  return value === '' ? null : Number(value)
}

function toPayload(values: WorkShiftFormValues): CreateWorkShiftPayload {
  return {
    code: values.code || null,
    early_leave_threshold_minutes: Number(values.early_leave_threshold_minutes),
    end_time: toApiTime(values.end_time),
    is_active: values.is_active,
    is_overnight: values.is_overnight,
    late_threshold_minutes: Number(values.late_threshold_minutes),
    name: values.name,
    required_work_minutes: toOptionalNumber(values.required_work_minutes),
    start_time: toApiTime(values.start_time),
  }
}

function getFormValues(shift?: WorkShift | null): WorkShiftFormValues {
  if (!shift) {
    return { ...defaultValues }
  }

  return {
    code: shift.code ?? '',
    early_leave_threshold_minutes: String(shift.early_leave_threshold_minutes),
    end_time: toTimeInput(shift.end_time),
    is_active: shift.is_active,
    is_overnight: shift.is_overnight,
    late_threshold_minutes: String(shift.late_threshold_minutes),
    name: shift.name,
    required_work_minutes: shift.required_work_minutes ? String(shift.required_work_minutes) : '',
    start_time: toTimeInput(shift.start_time),
  }
}

function getValidationErrors(values: WorkShiftFormValues): WorkShiftFormErrors {
  const result = workShiftSchema.safeParse(values)

  if (result.success) {
    return {}
  }

  return result.error.issues.reduce<WorkShiftFormErrors>((accumulator, issue) => {
    const fieldName = issue.path[0]

    if (typeof fieldName === 'string' && fieldName in values && !accumulator[fieldName as keyof WorkShiftFormValues]) {
      accumulator[fieldName as keyof WorkShiftFormValues] = issue.message
    }

    return accumulator
  }, {})
}

export function WorkShiftForm({ onCancelEdit, selectedShift }: WorkShiftFormProps) {
  const createWorkShift = useCreateWorkShift()
  const updateWorkShift = useUpdateWorkShift()
  const isEditing = Boolean(selectedShift)
  const [errors, setErrors] = useState<WorkShiftFormErrors>({})
  const [values, setValues] = useState<WorkShiftFormValues>(() => getFormValues(selectedShift))

  const setFieldValue = (fieldName: keyof WorkShiftFormValues, value: string | boolean) => {
    setValues((currentValues) => ({
      ...currentValues,
      [fieldName]: value,
    }))
    setErrors((currentErrors) => ({
      ...currentErrors,
      [fieldName]: undefined,
    }))
  }

  const handleTextChange =
    (fieldName: keyof WorkShiftFormValues) => (event: ChangeEvent<HTMLInputElement>) => {
      const nextValue = event.target.value

      if (fieldName === 'start_time' || fieldName === 'end_time') {
        setValues((currentValues) => {
          const nextValues = {
            ...currentValues,
            [fieldName]: nextValue,
          }
          const shouldSuggestOvernight =
            nextValues.start_time !== '' && nextValues.end_time !== '' && nextValues.start_time > nextValues.end_time

          return {
            ...nextValues,
            is_overnight: shouldSuggestOvernight ? true : nextValues.is_overnight,
          }
        })
        setErrors((currentErrors) => ({
          ...currentErrors,
          [fieldName]: undefined,
          is_overnight: undefined,
        }))
        return
      }

      setFieldValue(fieldName, nextValue)
    }

  const handleCheckboxChange =
    (fieldName: keyof WorkShiftFormValues) => (event: ChangeEvent<HTMLInputElement>) => {
      setFieldValue(fieldName, event.target.checked)
    }

  const resetForm = () => {
    setErrors({})
    setValues({ ...defaultValues })
  }

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const validationErrors = getValidationErrors(values)

    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      return
    }

    const payload = toPayload(values)

    if (selectedShift) {
      updateWorkShift.mutate(
        { payload, shiftId: selectedShift.shift_id },
        {
          onSuccess: () => {
            onCancelEdit?.()
            resetForm()
          },
        },
      )
      return
    }

    createWorkShift.mutate(payload, {
      onSuccess: resetForm,
    })
  }

  const mutationError = createWorkShift.error ?? updateWorkShift.error
  const isPending = createWorkShift.isPending || updateWorkShift.isPending

  return (
    <form className="resource-form" onSubmit={onSubmit}>
      <Input
        error={errors.name}
        label="Tên ca"
        name="name"
        onChange={handleTextChange('name')}
        value={values.name}
      />
      <Input
        error={errors.code}
        label="Mã ca"
        name="code"
        onChange={handleTextChange('code')}
        value={values.code}
      />
      <div className="form-grid">
        <Input
          error={errors.start_time}
          label="Bắt đầu"
          name="start_time"
          onChange={handleTextChange('start_time')}
          type="time"
          value={values.start_time}
        />
        <Input
          error={errors.end_time}
          label="Kết thúc"
          name="end_time"
          onChange={handleTextChange('end_time')}
          type="time"
          value={values.end_time}
        />
      </div>
      <div className="form-grid">
        <Input
          error={errors.late_threshold_minutes}
          inputMode="numeric"
          label="Ngưỡng đi trễ"
          name="late_threshold_minutes"
          onChange={handleTextChange('late_threshold_minutes')}
          value={values.late_threshold_minutes}
        />
        <Input
          error={errors.early_leave_threshold_minutes}
          inputMode="numeric"
          label="Ngưỡng về sớm"
          name="early_leave_threshold_minutes"
          onChange={handleTextChange('early_leave_threshold_minutes')}
          value={values.early_leave_threshold_minutes}
        />
      </div>
      <Input
        error={errors.required_work_minutes}
        inputMode="numeric"
        label="Số phút làm việc yêu cầu"
        name="required_work_minutes"
        onChange={handleTextChange('required_work_minutes')}
        placeholder="Để trống nếu backend tự tính"
        value={values.required_work_minutes}
      />
      <label className="checkbox-field">
        <input
          checked={values.is_overnight}
          name="is_overnight"
          onChange={handleCheckboxChange('is_overnight')}
          type="checkbox"
        />
        <span>Ca qua đêm</span>
      </label>
      <label className="checkbox-field">
        <input
          checked={values.is_active}
          name="is_active"
          onChange={handleCheckboxChange('is_active')}
          type="checkbox"
        />
        <span>Đang hoạt động</span>
      </label>
      {mutationError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(mutationError, 'Không thể lưu ca làm việc.')}
        </StatusMessage>
      ) : null}
      <div className="action-row">
        <Button isLoading={isPending} type="submit">
          {isEditing ? 'Cập nhật ca' : 'Tạo ca'}
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
