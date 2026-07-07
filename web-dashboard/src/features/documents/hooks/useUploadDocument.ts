import { useMutation, useQueryClient } from '@tanstack/react-query'
import { documentApi } from '@/features/documents/api/document.api'

export function useUploadDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: documentApi.uploadDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}
