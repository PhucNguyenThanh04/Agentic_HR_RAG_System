import { api } from '@/lib/axios'
import type {
  Conversation,
  NewMessageResponse,
  SendMessagePayload,
  SendMessageResponse,
  ChatMessage,
} from '@/features/chatbox/types/chatbox.types'

export const chatboxApi = {
  createConversation: async (): Promise<Conversation> => {
    const response = await api.post<Conversation>('/chat/')
    return response.data
  },
  listConversations: async (): Promise<Conversation[]> => {
    const response = await api.get<Conversation[]>('/chat/')
    return response.data
  },
  sendNewMessage: async (payload: SendMessagePayload): Promise<NewMessageResponse> => {
    const response = await api.post<NewMessageResponse>('/chat/new-message', payload)
    return response.data
  },
  deleteConversation: async (conversationId: string): Promise<void> => {
    await api.delete(`/chat/${conversationId}`)
  },
  listMessages: async (conversationId: string): Promise<ChatMessage[]> => {
    const response = await api.get<ChatMessage[]>(`/chat/${conversationId}/messages`)
    return response.data
  },
  sendMessage: async ({
    conversationId,
    payload,
  }: {
    conversationId: string
    payload: SendMessagePayload
  }): Promise<SendMessageResponse> => {
    const response = await api.post<SendMessageResponse>(`/chat/${conversationId}/messages`, payload)
    return response.data
  },
}
