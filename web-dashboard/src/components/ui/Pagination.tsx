import { Button } from '@/components/ui/Button'

type PaginationProps = {
  currentPage: number
  isFetching?: boolean
  onPageChange: (page: number) => void
  pageSize: number
  total: number
}

export function Pagination({
  currentPage,
  isFetching = false,
  onPageChange,
  pageSize,
  total,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="pagination">
      <span>
        Trang {currentPage}/{totalPages}
      </span>
      <div className="pagination__actions">
        <Button
          disabled={currentPage <= 1 || isFetching}
          onClick={() => onPageChange(currentPage - 1)}
          size="sm"
          variant="secondary"
        >
          Trước
        </Button>
        <Button
          disabled={currentPage >= totalPages || isFetching}
          onClick={() => onPageChange(currentPage + 1)}
          size="sm"
          variant="secondary"
        >
          Sau
        </Button>
      </div>
    </div>
  )
}
