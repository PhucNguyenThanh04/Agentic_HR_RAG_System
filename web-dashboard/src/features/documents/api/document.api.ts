import { api } from '@/lib/axios'
import type {
  DocumentItem,
  DocumentListParams,
  DocumentListResponse,
  UploadDocumentPayload,
} from '@/features/documents/types/document.types'

export const documentApi = {
  listDocuments: async (params: DocumentListParams): Promise<DocumentListResponse> => {
    const response = await api.get<DocumentListResponse>('/documents/', { params })
    return response.data
  },
  getDocument: async (documentId: string): Promise<DocumentItem> => {
    const response = await api.get<DocumentItem>(`/documents/${documentId}`)
    return response.data
  },
  uploadDocument: async (payload: UploadDocumentPayload): Promise<DocumentItem> => {
    const formData = new FormData()
    formData.append('title', payload.title)
    payload.allowed_roles.forEach((role) => formData.append('allowed_roles', role))
    formData.append('file', payload.file)

    const response = await api.post<DocumentItem>('/documents/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  deleteDocument: async (documentId: string): Promise<void> => {
    await api.delete(`/documents/${documentId}`)
  },
}
