type LoadingProps = {
  label?: string
}

export function Loading({ label = 'Đang tải dữ liệu' }: LoadingProps) {
  return (
    <div className="loading" role="status">
      <span className="loading__spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
