import type { ReactNode } from 'react'
import { cx } from '@/lib/utils'

type BadgeTone = 'blue' | 'green' | 'gray' | 'red' | 'amber' | 'teal'

type BadgeProps = {
  children: ReactNode
  tone?: BadgeTone
}

export function Badge({ children, tone = 'gray' }: BadgeProps) {
  return <span className={cx('badge', `badge--${tone}`)}>{children}</span>
}
