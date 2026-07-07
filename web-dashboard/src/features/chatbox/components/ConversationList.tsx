import { Button } from '@/components/ui/Button'
import type { Conversation } from '@/features/chatbox/types/chatbox.types'
import { cx, formatDateTime } from '@/lib/utils'

type ConversationListProps = {
  conversations: Conversation[]
  deletingConversationId?: string | null
  onDelete: (conversationId: string) => void
  onSelect: (conversationId: string) => void
  selectedConversationId: string | null
}

export function ConversationList({
  conversations,
  deletingConversationId,
  onDelete,
  onSelect,
  selectedConversationId,
}: ConversationListProps) {
  return (
    <div className="conversation-list">
      {conversations.map((conversation) => (
        <article
          className={cx(
            'conversation-item',
            selectedConversationId === conversation.id && 'conversation-item--active',
          )}
          key={conversation.id}
        >
          <button onClick={() => onSelect(conversation.id)} type="button">
            <strong>{conversation.title}</strong>
            <span>{formatDateTime(conversation.updated_at)}</span>
          </button>
          <Button
            isLoading={deletingConversationId === conversation.id}
            onClick={() => onDelete(conversation.id)}
            size="sm"
            variant="ghost"
          >
            Xóa
          </Button>
        </article>
      ))}
    </div>
  )
}
