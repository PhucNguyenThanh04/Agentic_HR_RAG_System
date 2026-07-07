import { useQuery } from '@tanstack/react-query'
import { chatboxApi } from '@/features/chatbox/api/chatbox.api'

export function useConversations() {
  return useQuery({
    queryFn: chatboxApi.listConversations,
    queryKey: ['chatbox', 'conversations'],
  })
}
