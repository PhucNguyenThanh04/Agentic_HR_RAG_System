import { useQuery } from '@tanstack/react-query'
import { documentApi } from '@/features/documents/api/document.api'
import type { DocumentListParams } from '@/features/documents/types/document.types'

export function useDocuments(params: DocumentListParams) {
  return useQuery({
    queryFn: () => documentApi.listDocuments(params),
    queryKey: ['documents', params],
  })
}
