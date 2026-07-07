import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Loading } from '@/components/ui/Loading'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { AskUserOptionsPanel } from '@/features/chatbox/components/AskUserOptionsPanel'
import { ChatComposer } from '@/features/chatbox/components/ChatComposer'
import { ChatMessageList } from '@/features/chatbox/components/ChatMessageList'
import { ConversationList } from '@/features/chatbox/components/ConversationList'
import { useConversationMessages } from '@/features/chatbox/hooks/useConversationMessages'
import { useConversations } from '@/features/chatbox/hooks/useConversations'
import { useCreateConversation } from '@/features/chatbox/hooks/useCreateConversation'
import { useDeleteConversation } from '@/features/chatbox/hooks/useDeleteConversation'
import { useSendMessage } from '@/features/chatbox/hooks/useSendMessage'
import type { Conversation } from '@/features/chatbox/types/chatbox.types'
import { getApiErrorMessage } from '@/lib/utils'

const EMPTY_CONVERSATIONS: Conversation[] = []

export function ChatboxPage() {
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null)
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const conversationsQuery = useConversations()
  const createConversation = useCreateConversation()
  const deleteConversation = useDeleteConversation()
  const sendMessage = useSendMessage()
  const conversations = conversationsQuery.data ?? EMPTY_CONVERSATIONS
  const pendingCreatedConversation =
    createConversation.data?.id === selectedConversationId ? createConversation.data : null
  const selectedConversation =
    conversations.find((conversation) => conversation.id === selectedConversationId) ??
    pendingCreatedConversation ??
    conversations[0] ??
    null
  const activeConversationId = selectedConversation?.id ?? null
  const messagesQuery = useConversationMessages(activeConversationId)
  const messages = messagesQuery.data ?? []
  const latestAskUserMessage = [...messages]
    .reverse()
    .find((message) => message.role === 'assistant' && message.ask_user && message.options?.length)

  const handleCreateConversation = () => {
    createConversation.mutate(undefined, {
      onSuccess: (conversation) => setSelectedConversationId(conversation.id),
    })
  }

  const handleDeleteConversation = (conversationId: string) => {
    const confirmed = window.confirm('Xóa hội thoại này và toàn bộ lịch sử tin nhắn?')
    if (!confirmed) {
      return
    }

    setDeletingConversationId(conversationId)
    deleteConversation.mutate(conversationId, {
      onSettled: () => setDeletingConversationId(null),
      onSuccess: () => {
        if (activeConversationId === conversationId) {
          setSelectedConversationId(null)
        }
      },
    })
  }

  const handleSend = async (message: string) => {
    let conversationId = activeConversationId

    if (!conversationId) {
      try {
        const conversation = await createConversation.mutateAsync(undefined)
        conversationId = conversation.id
        setSelectedConversationId(conversation.id)
      } catch (err) {
        console.error('Không thể tạo hội thoại mới:', err)
        return
      }
    }

    sendMessage.mutate({
      conversationId,
      payload: { message },
    })
  }

  const handleUseFreeText = () => {
    document.getElementById('chat-message-input')?.focus()
  }

  const activeError = sendMessage.error
  const isSending = sendMessage.isPending || createConversation.isPending
  const isSendError = sendMessage.isError

  return (
    <section className="chatbox-page">
      <div className="page-stack">
        <PageHeader
          description="Chat với RAG service qua /chat, có lưu conversation và message history."
          eyebrow="Chatbox"
          title="Trợ lý tài liệu nội bộ"
        />
        <div className="chat-shell">
          <aside className="chat-sidebar">
            <h2>Hội thoại</h2>
            <Button
              isLoading={createConversation.isPending}
              onClick={handleCreateConversation}
              variant="primary"
            >
              Tạo đoạn chat mới
            </Button>
            {createConversation.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(createConversation.error, 'Không thể tạo đoạn chat mới.')}
              </StatusMessage>
            ) : null}
            {conversationsQuery.isLoading ? <Loading label="Đang tải hội thoại" /> : null}
            {conversationsQuery.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(conversationsQuery.error, 'Không thể tải hội thoại.')}
              </StatusMessage>
            ) : null}
            {deleteConversation.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(deleteConversation.error, 'Không thể xóa hội thoại.')}
              </StatusMessage>
            ) : null}
            {!conversationsQuery.isLoading && !conversationsQuery.isError && conversations.length === 0 ? (
              <EmptyState
                description="Tạo đoạn chat mới, rồi gửi câu đầu tiên để backend tự đặt tiêu đề."
                title="Chưa có hội thoại"
              />
            ) : null}
            {conversations.length > 0 ? (
              <ConversationList
                conversations={conversations}
                deletingConversationId={deletingConversationId}
                onDelete={handleDeleteConversation}
                onSelect={setSelectedConversationId}
                selectedConversationId={activeConversationId}
              />
            ) : null}
          </aside>
          <main className="chat-main">
            <div className="chat-main__header">
              <div>
                <p className="eyebrow">Conversation</p>
                <h2>{selectedConversation?.title ?? 'Tin nhắn mới'}</h2>
              </div>
            </div>
            {activeConversationId && messagesQuery.isLoading ? <Loading label="Đang tải tin nhắn" /> : null}
            {messagesQuery.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(messagesQuery.error, 'Không thể tải tin nhắn.')}
              </StatusMessage>
            ) : null}
            {!activeConversationId ? (
              <EmptyState
                description="Tạo đoạn chat mới hoặc gửi câu hỏi đầu tiên để bắt đầu."
                title="Sẵn sàng trò chuyện"
              />
            ) : null}
            {activeConversationId && !messagesQuery.isLoading && messages.length === 0 ? (
              <EmptyState
                description="Gửi câu đầu tiên, backend sẽ dùng câu đó làm tiêu đề đoạn chat."
                title="Chưa có nội dung"
              />
            ) : null}
            {messages.length > 0 ? (
              <ChatMessageList
                messages={messages}
                onSendOption={handleSend}
              />
            ) : null}
            {latestAskUserMessage ? (
              <AskUserOptionsPanel
                message={latestAskUserMessage}
                onChooseOption={handleSend}
                onUseFreeText={handleUseFreeText}
              />
            ) : null}
            <ChatComposer
              error={activeError}
              isError={isSendError}
              isSending={isSending}
              onSend={handleSend}
              selectedConversationId={activeConversationId}
            />
          </main>
        </div>
      </div>
    </section>
  )
}
