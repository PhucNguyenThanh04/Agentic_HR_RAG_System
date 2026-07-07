import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { Textarea } from '@/components/ui/Textarea'
import { getApiErrorMessage } from '@/lib/utils'

type ChatComposerProps = {
  error: unknown
  isError: boolean
  isSending: boolean
  onSend: (message: string) => void
  selectedConversationId: string | null
}

export function ChatComposer({
  error,
  isError,
  isSending,
  onSend,
  selectedConversationId,
}: ChatComposerProps) {
  const [message, setMessage] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)

  const handleSubmit = (event?: React.FormEvent) => {
    event?.preventDefault()
    const trimmed = message.trim()
    if (!trimmed) {
      setValidationError('Vui lòng nhập nội dung')
      return
    }

    setValidationError(null)
    onSend(trimmed)
    setMessage('')
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit()
    }
  }

  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(event.target.value)
    if (validationError && event.target.value.trim()) {
      setValidationError(null)
    }
  }

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <Textarea
        error={validationError ?? undefined}
        id="chat-message-input"
        label={selectedConversationId ? 'Tin nhắn' : 'Tin nhắn đầu tiên'}
        placeholder="Nhập câu hỏi về chính sách, tài liệu hoặc quy trình..."
        rows={3}
        value={message}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />
      {isError ? (
        <StatusMessage tone="error">
          {getApiErrorMessage(error, 'Không thể gửi tin nhắn.')}
        </StatusMessage>
      ) : null}
      <Button isLoading={isSending} type="submit">
        Gửi
      </Button>
    </form>
  )
}
