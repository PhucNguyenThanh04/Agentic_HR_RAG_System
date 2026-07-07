import type { TextareaHTMLAttributes } from 'react'
import { cx } from '@/lib/utils'

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: string
  label?: string
}

export function Textarea({ className, error, id, label, ...props }: TextareaProps) {
  const textareaId = id ?? props.name

  return (
    <label className="field" htmlFor={textareaId}>
      {label ? <span className="field__label">{label}</span> : null}
      <textarea
        className={cx('input', 'textarea', error && 'input--error', className)}
        id={textareaId}
        {...props}
      />
      {error ? <span className="field__error">{error}</span> : null}
    </label>
  )
}
