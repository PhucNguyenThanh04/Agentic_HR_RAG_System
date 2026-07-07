import { useMutation, useQueryClient } from '@tanstack/react-query'
import { chatboxApi } from '@/features/chatbox/api/chatbox.api'

export function useDeleteConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: chatboxApi.deleteConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatbox'] })
    },
  })
}
