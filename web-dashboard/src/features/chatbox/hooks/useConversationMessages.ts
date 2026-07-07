import { useQuery } from '@tanstack/react-query'
import { chatboxApi } from '@/features/chatbox/api/chatbox.api'

export function useConversationMessages(conversationId: string | null) {
  return useQuery({
    enabled: Boolean(conversationId),
    queryFn: () => chatboxApi.listMessages(conversationId!),
    queryKey: ['chatbox', 'messages', conversationId],
  })
}
