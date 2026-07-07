import { Button } from '@/components/ui/Button'
import type { ChatMessage } from '@/features/chatbox/types/chatbox.types'

type AskUserOptionsPanelProps = {
  message: ChatMessage
  onChooseOption: (option: string) => void
  onUseFreeText: () => void
}

function formatOption(option: string | Record<string, unknown>): string {
  if (typeof option === 'string') {
    return option
  }

  const label = option.label ?? option.title ?? option.value
  return typeof label === 'string' ? label : JSON.stringify(option)
}

export function AskUserOptionsPanel({
  message,
  onChooseOption,
  onUseFreeText,
}: AskUserOptionsPanelProps) {
  const options = message.options ?? []

  if (!message.ask_user || options.length === 0) {
    return null
  }

  return (
    <section className="ask-user-panel" aria-label="Lựa chọn phản hồi">
      <div className="ask-user-panel__header">
        <strong>{message.content}</strong>
      </div>
      <div className="ask-user-panel__options">
        {options.map((option, index) => {
          const label = formatOption(option)

          return (
            <button key={`${message.id}-choice-${index}`} onClick={() => onChooseOption(label)} type="button">
              <span>{index + 1}</span>
              <strong>{label}</strong>
            </button>
          )
        })}
      </div>
      <div className="ask-user-panel__footer">
        <span>Tự nhập câu trả lời trong ô tin nhắn nếu các lựa chọn chưa phù hợp.</span>
        <Button size="sm" variant="secondary" onClick={onUseFreeText}>
          Tự nhập
        </Button>
      </div>
    </section>
  )
}
