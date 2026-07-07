import type { SelectHTMLAttributes } from 'react'
import { cx } from '@/lib/utils'

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  error?: string
  label?: string
}

export function Select({ children, className, error, id, label, ...props }: SelectProps) {
  const selectId = id ?? props.name

  return (
    <label className="field" htmlFor={selectId}>
      {label ? <span className="field__label">{label}</span> : null}
      <select
        className={cx('input', 'select', error && 'input--error', className)}
        id={selectId}
        {...props}
      >
        {children}
      </select>
      {error ? <span className="field__error">{error}</span> : null}
    </label>
  )
}
