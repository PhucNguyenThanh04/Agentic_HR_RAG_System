import type { ReactNode } from 'react'
import { cx } from '@/lib/utils'

type StatusMessageTone = 'error' | 'info' | 'success' | 'warning'

type StatusMessageProps = {
  children: ReactNode
  tone?: StatusMessageTone
}

export function StatusMessage({ children, tone = 'info' }: StatusMessageProps) {
  return <div className={cx('status-message', `status-message--${tone}`)}>{children}</div>
}
