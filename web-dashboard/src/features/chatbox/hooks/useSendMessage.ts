import { useMutation, useQueryClient } from '@tanstack/react-query'
import { tokenStorage } from '@/lib/storage'
import type { ChatMessage, SendMessageResponse } from '@/features/chatbox/types/chatbox.types'

function mergeMessages(current: ChatMessage[] | undefined, incoming: ChatMessage[]): ChatMessage[] {
  const messages = current ? [...current] : []

  incoming.forEach((message) => {
    const existingIndex = messages.findIndex((item) => item.id === message.id)
    if (existingIndex >= 0) {
      messages[existingIndex] = message
      return
    }

    messages.push(message)
  })

  return messages
}

export function useSendMessage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      conversationId,
      payload,
    }: {
      conversationId: string
      payload: { message: string }
    }): Promise<ChatMessage> => {
      const message = payload.message
      const token = tokenStorage.getAccessToken()

      const tempUserMsgId = `temp-user-${Date.now()}`
      const tempAssistantMsgId = `temp-assistant-${Date.now()}`

      const userMsg: ChatMessage = {
        id: tempUserMsgId,
        conversation_id: conversationId,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
        ask_user: false,
        citations: null,
        options: null,
      }

      const assistantMsg: ChatMessage = {
        id: tempAssistantMsgId,
        conversation_id: conversationId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString(),
        ask_user: false,
        citations: null,
        options: null,
        isStreaming: true,
        agent_status: 'Đang kết nối với AI...',
      }

      // Immediately insert placeholders
      queryClient.setQueryData<ChatMessage[]>(
        ['chatbox', 'messages', conversationId],
        (current) => mergeMessages(current, [userMsg, assistantMsg]),
      )

      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
      const response = await fetch(`${apiBaseUrl}/chat/${conversationId}/messages/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message }),
      })

      if (!response.ok) {
        // Rollback placeholders on network error
        queryClient.setQueryData<ChatMessage[]>(
          ['chatbox', 'messages', conversationId],
          (current) => current?.filter((m) => m.id !== tempUserMsgId && m.id !== tempAssistantMsgId) || [],
        )
        throw new Error('Gửi tin nhắn thất bại. Vui lòng kiểm tra lại kết nối.')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder('utf-8')
      if (!reader) {
        throw new Error('Không thể đọc luồng dữ liệu từ máy chủ.')
      }

      let accumulatedText = ''
      let finalData: SendMessageResponse | null = null
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          if (!part.trim()) continue

          let eventName = 'message'
          let dataContent = ''

          const lines = part.split('\n')
          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventName = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              dataContent += line.slice(5).trim()
            }
          }

          if (dataContent) {
            try {
              const dataPayload = JSON.parse(dataContent)

              if (eventName === 'status') {
                const statusMsg = dataPayload.message || 'Đang xử lý...'
                queryClient.setQueryData<ChatMessage[]>(
                  ['chatbox', 'messages', conversationId],
                  (current) =>
                    current?.map((m) =>
                      m.id === tempAssistantMsgId ? { ...m, agent_status: statusMsg } : m,
                    ) || [],
                )
              } else if (eventName === 'delta') {
                const text = dataPayload.text || ''
                accumulatedText += text
                queryClient.setQueryData<ChatMessage[]>(
                  ['chatbox', 'messages', conversationId],
                  (current) =>
                    current?.map((m) =>
                      m.id === tempAssistantMsgId ? { ...m, content: accumulatedText } : m,
                    ) || [],
                )
              } else if (eventName === 'final') {
                finalData = dataPayload
              } else if (eventName === 'error') {
                throw new Error(dataPayload.message || 'Có lỗi xảy ra trong quá trình xử lý.')
              }
            } catch (err) {
              console.error('Lỗi phân tích SSE:', err)
            }
          }
        }
      }

      if (finalData) {
        const officialUserMsg = finalData.user_message
        const officialAssistantMsg = {
          ...finalData.assistant_message,
          ask_user: finalData.assistant_message.ask_user || finalData.ask_user,
          citations: finalData.assistant_message.citations?.length
            ? finalData.assistant_message.citations
            : finalData.citations,
          options: finalData.assistant_message.options?.length
            ? finalData.assistant_message.options
            : finalData.options,
        }

        queryClient.setQueryData<ChatMessage[]>(
          ['chatbox', 'messages', conversationId],
          (current) => {
            const filtered = current?.filter(
              (m) => m.id !== tempUserMsgId && m.id !== tempAssistantMsgId,
            ) || []
            return mergeMessages(filtered, [officialUserMsg, officialAssistantMsg])
          },
        )

        queryClient.invalidateQueries({ queryKey: ['chatbox', 'conversations'] })
        return officialAssistantMsg
      }

      throw new Error('Không nhận được phản hồi hoàn chỉnh từ AI.')
    },
  })
}

