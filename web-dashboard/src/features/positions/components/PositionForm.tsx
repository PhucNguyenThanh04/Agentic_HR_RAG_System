import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useCreatePosition } from '@/features/positions/hooks/useCreatePosition'
import { positionSchema, type PositionFormValues } from '@/features/positions/schemas/position.schema'
import { getApiErrorMessage } from '@/lib/utils'

export function PositionForm() {
  const createPosition = useCreatePosition()
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<PositionFormValues>({
    resolver: zodResolver(positionSchema),
    defaultValues: {
      code: '',
      description: '',
      is_active: true,
      name: '',
    },
  })

  const onSubmit = (values: PositionFormValues) => {
    createPosition.mutate(
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
      <Input error={errors.name?.message} label="Tên chức vụ" {...register('name')} />
      <Input error={errors.code?.message} label="Mã" {...register('code')} />
      <Input error={errors.description?.message} label="Mô tả" {...register('description')} />
      <label className="checkbox-field">
        <input type="checkbox" {...register('is_active')} />
        <span>Đang hoạt động</span>
      </label>
      {createPosition.isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(createPosition.error, 'Không thể tạo chức vụ.')}
        </StatusMessage>
      ) : null}
      <Button isLoading={createPosition.isPending} type="submit">
        Tạo chức vụ
      </Button>
    </form>
  )
}
