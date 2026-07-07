import { useQuery } from '@tanstack/react-query'
import { positionApi } from '@/features/positions/api/position.api'

export function usePositions(search?: string, enabled = true) {
  return useQuery({
    enabled,
    queryFn: () => positionApi.listPositions(search),
    queryKey: ['positions', search],
  })
}
