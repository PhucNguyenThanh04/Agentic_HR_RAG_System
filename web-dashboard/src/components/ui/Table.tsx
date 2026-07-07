import type { ReactNode } from 'react'
import { cx } from '@/lib/utils'

type TableProps = {
  children: ReactNode
  className?: string
}

export function Table({ children, className }: TableProps) {
  return (
    <div className={cx('table-shell', className)}>
      <table className="table">{children}</table>
    </div>
  )
}
