import { z } from 'zod'

export const sendMessageSchema = z.object({
  message: z.string().trim().min(1, 'Vui lòng nhập nội dung'),
})

export type SendMessageFormValues = z.infer<typeof sendMessageSchema>
