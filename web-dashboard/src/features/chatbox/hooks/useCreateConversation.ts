import { useMutation, useQueryClient } from '@tanstack/react-query'
import { chatboxApi } from '@/features/chatbox/api/chatbox.api'

export function useCreateConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: chatboxApi.createConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatbox', 'conversations'] })
    },
  })
}
