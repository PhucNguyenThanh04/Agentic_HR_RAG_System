import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useUploadDocument } from '@/features/documents/hooks/useUploadDocument'
import {
  documentUploadSchema,
  type DocumentUploadFormValues,
} from '@/features/documents/schemas/document.schema'
import { getApiErrorMessage } from '@/lib/utils'
import type { RoleName } from '@/types/common.types'

const roleOptions: Array<{ label: string; value: RoleName }> = [
  { label: 'Admin', value: 'admin' },
  { label: 'HR', value: 'hr' },
  { label: 'Manager', value: 'manager' },
  { label: 'Employee', value: 'employee' },
]

export function DocumentUploadForm() {
  const uploadDocument = useUploadDocument()
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<DocumentUploadFormValues>({
    resolver: zodResolver(documentUploadSchema),
    defaultValues: {
      allowed_roles: ['admin'],
      title: '',
    },
  })

  const onSubmit = (values: DocumentUploadFormValues) => {
    const file = values.file.item(0)
    if (!file) {
      return
    }

    uploadDocument.mutate(
      {
        allowed_roles: values.allowed_roles,
        file,
        title: values.title,
      },
      {
        onSuccess: () => reset(),
      },
    )
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit(onSubmit)}>
      <Input error={errors.title?.message} label="Tiêu đề tài liệu" {...register('title')} />
      <Input
        accept=".pdf,.txt,.docx"
        error={errors.file?.message}
        label="File"
        type="file"
        {...register('file')}
      />
      <fieldset className="checkbox-group">
        <legend>Role được phép truy xuất</legend>
        {roleOptions.map((role) => (
          <label className="checkbox-field" key={role.value}>
            <input type="checkbox" value={role.value} {...register('allowed_roles')} />
            <span>{role.label}</span>
          </label>
        ))}
        {errors.allowed_roles?.message ? (
          <span className="field__error">{errors.allowed_roles.message}</span>
        ) : null}
      </fieldset>
      {uploadDocument.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(uploadDocument.error, 'Không thể upload tài liệu.')}
        </StatusMessage>
      ) : null}
      {uploadDocument.isSuccess ? (
        <StatusMessage tone="success">Tài liệu đã được thêm vào vector store.</StatusMessage>
      ) : null}
      <Button isLoading={uploadDocument.isPending} type="submit">
        Thêm tài liệu
      </Button>
    </form>
  )
}
