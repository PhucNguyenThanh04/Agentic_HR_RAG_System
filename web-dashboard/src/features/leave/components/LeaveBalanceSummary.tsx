import type { LeaveBalance } from '../types/leave.types'

type LeaveBalanceSummaryProps = {
  balance?: LeaveBalance
  isLoading: boolean
}

export function LeaveBalanceSummary({ balance, isLoading }: LeaveBalanceSummaryProps) {
  if (isLoading) {
    return (
      <div className="stat-grid">
        <article className="stat-card stat-card--gray">
          <span>Đang tải số dư...</span>
          <strong>--</strong>
        </article>
      </div>
    )
  }

  if (!balance) {
    return (
      <div className="stat-grid">
        <article className="stat-card stat-card--gray">
          <span>Chưa có thông tin số dư nghỉ phép</span>
          <strong>--</strong>
        </article>
      </div>
    )
  }

  return (
    <div className="page-stack">
      <div className="stat-grid">
        <article className="stat-card stat-card--blue">
          <span>Tổng số ngày được phép nghỉ ({balance.year})</span>
          <strong>{balance.total_allowed_days} ngày</strong>
        </article>
        <article className="stat-card stat-card--amber">
          <span>Số ngày đã nghỉ</span>
          <strong>{balance.total_used_days} ngày</strong>
        </article>
        <article className="stat-card stat-card--teal">
          <span>Số ngày còn lại</span>
          <strong>{balance.total_remaining_days} ngày</strong>
        </article>
      </div>

      <div className="panel">
        <div className="panel__header">
          <h2>Chi tiết theo loại phép</h2>
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Loại phép</th>
                <th>Mã phép</th>
                <th>Hình thức</th>
                <th>Tối đa / năm</th>
                <th>Đã dùng</th>
                <th>Còn lại</th>
              </tr>
            </thead>
            <tbody>
              {balance.items.map((item) => (
                <tr key={item.leave_type_id}>
                  <td>
                    <strong>{item.name}</strong>
                  </td>
                  <td>
                    <code>{item.code || '-'}</code>
                  </td>
                  <td>
                    <span className={`badge badge--${item.is_paid ? 'teal' : 'gray'}`}>
                      {item.is_paid ? 'Có lương' : 'Không lương'}
                    </span>
                  </td>
                  <td>{item.max_days_per_year !== null ? `${item.max_days_per_year} ngày` : 'Không giới hạn'}</td>
                  <td>{item.used_days} ngày</td>
                  <td>
                    {item.remaining_days !== null ? (
                      <span className="font-semibold text-teal-600">{item.remaining_days} ngày</span>
                    ) : (
                      'Không giới hạn'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
