import { z } from 'zod'

export const onboardingSchema = z.object({
  email: z.string().trim().email('Email không hợp lệ'),
  password: z
    .string()
    .min(8, 'Mật khẩu tối thiểu 8 ký tự')
    .regex(/[A-Za-z]/, 'Mật khẩu cần có chữ cái')
    .regex(/[0-9]/, 'Mật khẩu cần có số'),
  full_name: z.string().trim().min(1, 'Vui lòng nhập họ tên').max(120),
  department_id: z.coerce.number().min(1, 'Vui lòng chọn phòng ban'),
  position_id: z.coerce.number().min(1, 'Vui lòng chọn chức vụ'),
})

export type OnboardingFormInput = z.input<typeof onboardingSchema>
export type OnboardingFormValues = z.output<typeof onboardingSchema>
