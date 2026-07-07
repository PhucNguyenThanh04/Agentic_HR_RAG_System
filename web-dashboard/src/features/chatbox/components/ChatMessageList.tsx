import { useEffect, useRef } from 'react'
import { Badge } from '@/components/ui/Badge'
import type { ChatMessage } from '@/features/chatbox/types/chatbox.types'
import { cx, formatDateTime } from '@/lib/utils'

type ChatMessageListProps = {
  messages: ChatMessage[]
  onSendOption: (option: string) => void
}

function formatOption(option: string | Record<string, unknown>): string {
  if (typeof option === 'string') {
    return option
  }

  const label = option.label ?? option.title ?? option.value
  return typeof label === 'string' ? label : JSON.stringify(option)
}

function getStringValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function getNumberValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  return null
}

function getCitationMetadata(citation: Record<string, unknown>) {
  const metadata = typeof citation.metadata === 'object' && citation.metadata !== null
    ? citation.metadata as Record<string, unknown>
    : {}

  const rawTitle =
    getStringValue(citation.title) ??
    getStringValue(citation.filename) ??
    getStringValue(citation.file_name) ??
    getStringValue(metadata.title) ??
    getStringValue(metadata.filename) ??
    getStringValue(metadata.file_name) ??
    getStringValue(citation.document_id)
  const title = rawTitle?.replace(/^[0-9a-f-]{36}_/i, '') ?? 'Tài liệu không rõ tên'
  const page =
    getNumberValue(citation.page) ??
    getNumberValue(citation.page_number) ??
    getNumberValue(metadata.page) ??
    getNumberValue(metadata.page_number)
  const section =
    getStringValue(citation.section) ??
    getStringValue(citation.clause_number) ??
    getStringValue(metadata.section) ??
    getStringValue(metadata.clause_number)

  return { page, section, title }
}

function getCitationIndex(citation: Record<string, unknown>, index: number): number {
  return getNumberValue(citation.index) ?? index + 1
}

export function ChatMessageList({ messages, onSendOption }: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-thread">
      {messages.map((message) => (
        <article className={cx('chat-bubble', `chat-bubble--${message.role}`)} key={message.id}>
          <div className="chat-bubble__meta">
            <Badge tone={message.role === 'assistant' ? 'teal' : 'blue'}>
              {message.role === 'assistant' ? 'Assistant' : 'Bạn'}
            </Badge>
            <span>{formatDateTime(message.created_at)}</span>
          </div>
          
          {message.content ? (
            <p className={cx(message.isStreaming && 'streaming-cursor')}>{message.content}</p>
          ) : (
            message.isStreaming && (
              <div className="agent-thinking-status">
                <span className="thinking-spinner"></span>
                <span>{message.agent_status || 'Đang chuẩn bị...'}</span>
              </div>
            )
          )}

          {message.isStreaming && message.content && message.agent_status ? (
            <div className="agent-thinking-status agent-thinking-status--inline">
              <span className="thinking-spinner"></span>
              <span>{message.agent_status}</span>
            </div>
          ) : null}

          {message.citations?.length ? (
            <div className="citation-list">
              <span className="citation-list__title">Nguồn tham khảo</span>
              {message.citations.map((citation, index) => {
                const metadata = getCitationMetadata(citation)
                const citationIndex = getCitationIndex(citation, index)

                return (
                  <span className="citation-chip" key={`${message.id}-${index}`}>
                    <strong>[{citationIndex}] {metadata.title}</strong>
                    <small>
                      {metadata.page ? `Trang ${metadata.page}` : 'Chưa có số trang'}
                      {metadata.section ? ` · ${metadata.section}` : ''}
                    </small>
                  </span>
                )
              })}
            </div>
          ) : null}
          {message.options?.length ? (
            <div className="option-list">
              {message.options.map((option, index) => {
                const label = formatOption(option)
                return (
                  <button key={`${message.id}-option-${index}`} onClick={() => onSendOption(label)} type="button">
                    {index + 1}. {label}
                  </button>
                )
              })}
            </div>
          ) : null}
        </article>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
