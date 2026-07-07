import { z } from 'zod'

const passwordSchema = z
  .string()
  .min(8, 'Mật khẩu tối thiểu 8 ký tự')
  .max(128, 'Mật khẩu tối đa 128 ký tự')
  .regex(/[A-Za-z]/, 'Mật khẩu cần có ít nhất một chữ cái')
  .regex(/[0-9]/, 'Mật khẩu cần có ít nhất một chữ số')

export const requestOtpSchema = z.object({
  email: z.string().trim().email('Email không hợp lệ'),
})

export const verifyOtpSchema = z.object({
  otp: z.string().trim().regex(/^\d{6}$/, 'OTP gồm 6 chữ số'),
})

export const confirmPasswordResetSchema = z
  .object({
    newPassword: passwordSchema,
    confirmPassword: z.string().min(1, 'Vui lòng nhập lại mật khẩu'),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: 'Mật khẩu nhập lại không khớp',
    path: ['confirmPassword'],
  })

export type RequestOtpFormValues = z.infer<typeof requestOtpSchema>
export type VerifyOtpFormValues = z.infer<typeof verifyOtpSchema>
export type ConfirmPasswordResetFormValues = z.infer<typeof confirmPasswordResetSchema>
