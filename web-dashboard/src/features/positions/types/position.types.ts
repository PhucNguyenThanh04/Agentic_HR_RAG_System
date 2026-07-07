export type Position = {
  position_id: number
  name: string
  code: string | null
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type CreatePositionPayload = {
  name: string
  code?: string | null
  description?: string | null
  is_active: boolean
}
