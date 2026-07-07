import { z } from 'zod'
import type { RoleName } from '@/types/common.types'

const allowedRoleValues = ['admin', 'hr', 'manager', 'employee'] as const

export const documentUploadSchema = z.object({
  allowed_roles: z.array(z.enum(allowedRoleValues)).min(1, 'Chọn ít nhất một role'),
  file: z
    .instanceof(FileList)
    .refine((files) => files.length === 1, 'Vui lòng chọn một file')
    .refine((files) => files.item(0)?.size !== 0, 'File không được rỗng')
    .refine((files) => {
      const file = files.item(0)
      return Boolean(file && file.size <= 25 * 1024 * 1024)
    }, 'File phải nhỏ hơn 25MB')
    .refine((files) => {
      const file = files.item(0)
      return Boolean(file && /\.(pdf|txt|docx)$/i.test(file.name))
    }, 'Chỉ hỗ trợ PDF, TXT hoặc DOCX'),
  title: z.string().trim().min(1, 'Vui lòng nhập tiêu đề').max(300, 'Tối đa 300 ký tự'),
})

export type DocumentUploadFormValues = {
  allowed_roles: RoleName[]
  file: FileList
  title: string
}
