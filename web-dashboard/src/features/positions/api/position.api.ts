import { api } from '@/lib/axios'
import type { CreatePositionPayload, Position } from '@/features/positions/types/position.types'

export const positionApi = {
  listPositions: async (search?: string): Promise<Position[]> => {
    const response = await api.get<Position[]>('/positions/', {
      params: { search: search || undefined },
    })
    return response.data
  },
  createPosition: async (payload: CreatePositionPayload): Promise<Position> => {
    const response = await api.post<Position>('/positions/', payload)
    return response.data
  },
}
