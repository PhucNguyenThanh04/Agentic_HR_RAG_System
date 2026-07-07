import type { InputHTMLAttributes } from 'react'
import { cx } from '@/lib/utils'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: string
  label?: string
}

export function Input({ className, error, id, label, ...props }: InputProps) {
  const inputId = id ?? props.name

  return (
    <label className="field" htmlFor={inputId}>
      {label ? <span className="field__label">{label}</span> : null}
      <input
        className={cx('input', error && 'input--error', className)}
        id={inputId}
        {...props}
      />
      {error ? <span className="field__error">{error}</span> : null}
    </label>
  )
}
