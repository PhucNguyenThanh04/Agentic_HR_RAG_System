import { useMutation, useQueryClient } from '@tanstack/react-query'
import { positionApi } from '@/features/positions/api/position.api'

export function useCreatePosition() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: positionApi.createPosition,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['positions'] })
    },
  })
}
