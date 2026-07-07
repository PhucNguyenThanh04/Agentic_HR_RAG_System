import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useCreateDepartment } from '@/features/departments/hooks/useCreateDepartment'
import {
  departmentSchema,
  type DepartmentFormValues,
} from '@/features/departments/schemas/department.schema'
import { getApiErrorMessage } from '@/lib/utils'

export function DepartmentForm() {
  const createDepartment = useCreateDepartment()
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<DepartmentFormValues>({
    resolver: zodResolver(departmentSchema),
    defaultValues: {
      code: '',
      description: '',
      is_active: true,
      name: '',
    },
  })

  const onSubmit = (values: DepartmentFormValues) => {
    createDepartment.mutate(
      {
        code: values.code || null,
        description: values.description || null,
        is_active: values.is_active,
        name: values.name,
      },
      {
        onSuccess: () => reset(),
      },
    )
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit(onSubmit)}>
      <Input error={errors.name?.message} label="Tên phòng ban" {...register('name')} />
      <Input error={errors.code?.message} label="Mã" {...register('code')} />
      <Input error={errors.description?.message} label="Mô tả" {...register('description')} />
      <label className="checkbox-field">
        <input type="checkbox" {...register('is_active')} />
        <span>Đang hoạt động</span>
      </label>
      {createDepartment.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(createDepartment.error, 'Không thể tạo phòng ban.')}
        </StatusMessage>
      ) : null}
      <Button isLoading={createDepartment.isPending} type="submit">
        Tạo phòng ban
      </Button>
    </form>
  )
}
