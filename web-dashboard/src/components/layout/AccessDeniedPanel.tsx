import { StatusMessage } from '@/components/ui/StatusMessage'

export function AccessDeniedPanel() {
  return (
    <section className="access-denied">
      <div className="access-denied__content">
        <p className="eyebrow">Access denied</p>
        <h2>Bạn không có quyền truy cập dashboard</h2>
        <StatusMessage tone="warning">
          Tài khoản employee sử dụng mobile app. Web dashboard chỉ dành cho admin, HR và manager.
        </StatusMessage>
      </div>
    </section>
  )
}
