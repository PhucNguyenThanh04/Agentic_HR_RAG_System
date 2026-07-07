import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Textarea } from '@/components/ui/Textarea'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { getApiErrorMessage } from '@/lib/utils'
import type { LeaveTimeType } from '../types/leave.types'

// Wait, the hook is in '../hooks/useLeave'!
import { useCreateLeaveRequest as useCreateMutation, useLeaveTypes as useTypesQuery } from '../hooks/useLeave'

type LeaveRequestFormModalProps = {
  isOpen: boolean
  onClose: () => void
}

type FormValues = {
  leave_type_id: string
  start_date: string
  end_date: string
  time_type: LeaveTimeType
  total_days: string
  reason: string
}

function getToday(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

const initialValues: FormValues = {
  leave_type_id: '',
  start_date: getToday(),
  end_date: getToday(),
  time_type: 'full_day',
  total_days: '1',
  reason: '',
}

export function LeaveRequestFormModal({ isOpen, onClose }: LeaveRequestFormModalProps) {
  const [values, setValues] = useState<FormValues>(initialValues)
  const typesQuery = useTypesQuery()
  const createMutation = useCreateMutation()

  if (!isOpen) {
    return null
  }

  const activeTypes = (typesQuery.data ?? []).filter((t) => t.is_active)

  const handleChange = (fieldName: keyof FormValues) => (
    event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    setValues((current) => ({
      ...current,
      [fieldName]: event.target.value,
    }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!values.leave_type_id || !values.start_date || !values.end_date) {
      return
    }

    const payload = {
      leave_type_id: Number(values.leave_type_id),
      start_date: values.start_date,
      end_date: values.end_date,
      time_type: values.time_type,
      total_days: values.time_type === 'custom' ? Number(values.total_days) : undefined,
      reason: values.reason || undefined,
    }

    createMutation.mutate(payload, {
      onSuccess: () => {
        onClose()
        setValues(initialValues)
      },
    })
  }

  const isFormValid =
    values.leave_type_id &&
    values.start_date &&
    values.end_date &&
    (values.time_type !== 'custom' || (Number(values.total_days) > 0 && !isNaN(Number(values.total_days))))

  return (
    <div aria-modal="true" className="modal-backdrop" role="dialog">
      <section className="modal">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Request Leave</p>
            <h2>Đăng ký nghỉ phép</h2>
          </div>
          <Button onClick={onClose} size="sm" variant="secondary">
            Đóng
          </Button>
        </div>
        <form className="resource-form" onSubmit={handleSubmit}>
          <Select
            label="Loại nghỉ phép"
            name="leave_type_id"
            onChange={handleChange('leave_type_id')}
            value={values.leave_type_id}
          >
            <option value="">Chọn loại phép</option>
            {activeTypes.map((type) => (
              <option key={type.leave_type_id} value={type.leave_type_id}>
                {type.name} {type.is_paid ? '(Có lương)' : '(Không lương)'}
              </option>
            ))}
          </Select>

          <div className="grid grid--2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="Từ ngày"
              name="start_date"
              onChange={handleChange('start_date')}
              type="date"
              value={values.start_date}
            />
            <Input
              label="Đến ngày"
              name="end_date"
              onChange={handleChange('end_date')}
              type="date"
              value={values.end_date}
            />
          </div>

          <Select
            label="Hình thức thời gian"
            name="time_type"
            onChange={handleChange('time_type')}
            value={values.time_type}
          >
            <option value="full_day">Cả ngày (Full Day)</option>
            <option value="morning">Buổi sáng (Morning)</option>
            <option value="afternoon">Buổi chiều (Afternoon)</option>
            <option value="custom">Tự chọn số ngày (Custom)</option>
          </Select>

          {values.time_type === 'custom' ? (
            <Input
              label="Tổng số ngày nghỉ"
              min="0.1"
              name="total_days"
              onChange={handleChange('total_days')}
              step="0.1"
              type="number"
              value={values.total_days}
            />
          ) : null}

          <Textarea
            label="Lý do xin nghỉ"
            name="reason"
            onChange={handleChange('reason')}
            placeholder="Nêu rõ lý do nghỉ phép..."
            value={values.reason}
          />

          {createMutation.isError ? (
            <StatusMessage tone="error">
              {getApiErrorMessage(createMutation.error, 'Không thể gửi yêu cầu nghỉ phép.')}
            </StatusMessage>
          ) : null}

          <Button disabled={!isFormValid} isLoading={createMutation.isPending} type="submit">
            Gửi yêu cầu
          </Button>
        </form>
      </section>
    </div>
  )
}
