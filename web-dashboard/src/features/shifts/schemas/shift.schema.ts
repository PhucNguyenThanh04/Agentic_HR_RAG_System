import { z } from 'zod'

const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/
const integerPattern = /^\d+$/

function validateMinutes(value: string, min: number, max: number): boolean {
  return value === '' || (integerPattern.test(value) && Number(value) >= min && Number(value) <= max)
}

export const workShiftSchema = z
  .object({
    code: z.string().trim().max(30, 'Mã ca tối đa 30 ký tự').optional(),
    early_leave_threshold_minutes: z
      .string()
      .trim()
      .refine((value) => validateMinutes(value, 0, 240), 'Ngưỡng về sớm phải từ 0 đến 240 phút'),
    end_time: z.string().regex(timePattern, 'Giờ kết thúc không hợp lệ'),
    is_active: z.boolean(),
    is_overnight: z.boolean(),
    late_threshold_minutes: z
      .string()
      .trim()
      .refine((value) => validateMinutes(value, 0, 240), 'Ngưỡng đi trễ phải từ 0 đến 240 phút'),
    name: z.string().trim().min(1, 'Nhập tên ca').max(100, 'Tên ca tối đa 100 ký tự'),
    required_work_minutes: z
      .string()
      .trim()
      .refine((value) => validateMinutes(value, 0, 1440), 'Số phút làm việc phải từ 0 đến 1440'),
    start_time: z.string().regex(timePattern, 'Giờ bắt đầu không hợp lệ'),
  })
  .superRefine((values, context) => {
    if (values.start_time === values.end_time) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Giờ bắt đầu và kết thúc không được trùng nhau',
        path: ['end_time'],
      })
      return
    }

    if (values.is_overnight && values.end_time > values.start_time) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Ca qua đêm cần giờ kết thúc nhỏ hơn giờ bắt đầu',
        path: ['end_time'],
      })
      return
    }

    if (!values.is_overnight && values.end_time < values.start_time) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Ca trong ngày cần giờ kết thúc lớn hơn giờ bắt đầu',
        path: ['end_time'],
      })
    }
  })

export type WorkShiftFormValues = z.infer<typeof workShiftSchema>

export const shiftAssignmentSchema = z
  .object({
    effective_date: z.string().min(1, 'Chọn ngày bắt đầu'),
    employee_id: z.string().min(1, 'Chọn nhân viên'),
    end_date: z.string(),
    shift_id: z.string().min(1, 'Chọn ca làm việc'),
  })
  .superRefine((values, context) => {
    if (values.end_date && values.end_date < values.effective_date) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: 'Ngày kết thúc phải sau hoặc bằng ngày bắt đầu',
        path: ['end_date'],
      })
    }
  })

export type ShiftAssignmentFormValues = z.infer<typeof shiftAssignmentSchema>
