import { useMutation, useQueryClient } from '@tanstack/react-query'
import { documentApi } from '@/features/documents/api/document.api'

export function useDeleteDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: documentApi.deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}
