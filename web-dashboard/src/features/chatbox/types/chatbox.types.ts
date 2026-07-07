import type { UUID } from '@/types/common.types'

export type ChatMessageRole = 'user' | 'assistant'

export type Conversation = {
  created_at: string
  employee_id: UUID
  id: UUID
  title: string
  updated_at: string
}

export type ChatMessage = {
  ask_user: boolean
  citations: Array<Record<string, unknown>> | null
  content: string
  conversation_id: UUID
  created_at: string
  id: UUID
  options: Array<string | Record<string, unknown>> | null
  role: ChatMessageRole
  isStreaming?: boolean
  agent_status?: string
}


export type SendMessagePayload = {
  message: string
}

export type SendMessageResponse = {
  allow_free_text: boolean
  answer: string
  ask_user: boolean
  assistant_message: ChatMessage
  citations: Array<Record<string, unknown>>
  error_code: string | null
  finish_reason: string
  low_confidence: boolean
  options: string[]
  used_context: boolean
  user_message: ChatMessage
}

export type NewMessageResponse = SendMessageResponse & {
  conversation: Conversation
}
