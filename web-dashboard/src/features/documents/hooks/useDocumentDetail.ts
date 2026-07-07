import { useQuery } from '@tanstack/react-query'
import { documentApi } from '@/features/documents/api/document.api'

export function useDocumentDetail(documentId: string | null) {
  return useQuery({
    enabled: Boolean(documentId),
    queryFn: () => documentApi.getDocument(documentId!),
    queryKey: ['documents', 'detail', documentId],
  })
}
