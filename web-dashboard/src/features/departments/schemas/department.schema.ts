import { z } from 'zod'

export const departmentSchema = z.object({
  name: z.string().trim().min(1, 'Vui lòng nhập tên phòng ban').max(100),
  code: z.string().trim().max(30).optional(),
  description: z.string().trim().max(500).optional(),
  is_active: z.boolean(),
})

export type DepartmentFormValues = z.infer<typeof departmentSchema>
