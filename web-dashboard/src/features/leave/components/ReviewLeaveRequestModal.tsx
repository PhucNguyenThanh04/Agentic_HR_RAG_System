import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Textarea } from '@/components/ui/Textarea'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useReviewLeaveRequest } from '../hooks/useLeave'
import { getApiErrorMessage } from '@/lib/utils'
import type { LeaveRequest } from '../types/leave.types'

type ReviewLeaveRequestModalProps = {
  isOpen: boolean
  onClose: () => void
  request: LeaveRequest | null
  employeeName: string
  leaveTypeName: string
}

export function ReviewLeaveRequestModal({
  isOpen,
  onClose,
  request,
  employeeName,
  leaveTypeName,
}: ReviewLeaveRequestModalProps) {
  const [comment, setComment] = useState('')
  const [rejectionReason, setRejectionReason] = useState('')
  const [errorText, setErrorText] = useState('')
  const reviewMutation = useReviewLeaveRequest()

  if (!isOpen || !request) {
    return null
  }

  const handleReview = (action: 'approved' | 'rejected') => (event: FormEvent) => {
    event.preventDefault()
    setErrorText('')

    if (action === 'rejected' && !rejectionReason.trim()) {
      setErrorText('Vui lòng nhập lý do từ chối.')
      return
    }

    reviewMutation.mutate(
      {
        requestId: request.request_id,
        payload: {
          action,
          comment: comment.trim() || undefined,
          rejection_reason: action === 'rejected' ? rejectionReason.trim() : undefined,
        },
      },
      {
        onSuccess: () => {
          onClose()
          setComment('')
          setRejectionReason('')
        },
      }
    )
  }

  return (
    <div aria-modal="true" className="modal-backdrop" role="dialog">
      <section className="modal">
        <div className="panel__header">
          <div>
            <p className="eyebrow">Review Request</p>
            <h2>Duyệt đơn nghỉ phép</h2>
          </div>
          <Button onClick={onClose} size="sm" variant="secondary">
            Đóng
          </Button>
        </div>

        <div className="resource-form">
          <div className="detail-grid" style={{ marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div>
              <strong>Nhân viên:</strong> {employeeName}
            </div>
            <div>
              <strong>Loại phép:</strong> {leaveTypeName}
            </div>
            <div>
              <strong>Thời gian nghỉ:</strong> {request.start_date} đến {request.end_date} (
              {request.total_days} ngày)
            </div>
            {request.reason ? (
              <div>
                <strong>Lý do nghỉ:</strong> <em>{request.reason}</em>
              </div>
            ) : null}
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '1rem 0' }} />

          <form onSubmit={handleReview('approved')}>
            <Textarea
              label="Phản hồi / Ghi chú (Không bắt buộc)"
              name="comment"
              onChange={(e) => setComment(e.target.value)}
              placeholder="Nhập ghi chú cho nhân viên..."
              value={comment}
            />

            <div style={{ marginTop: '1rem' }} />

            {reviewMutation.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(reviewMutation.error, 'Không thể thực hiện phê duyệt.')}
              </StatusMessage>
            ) : null}

            {errorText ? <StatusMessage tone="warning">{errorText}</StatusMessage> : null}

            <div className="grid grid--2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1.5rem' }}>
              <Button
                isLoading={reviewMutation.isPending}
                onClick={handleReview('approved')}
                type="submit"
                variant="primary"
              >
                Phê duyệt
              </Button>
              <Button
                isLoading={reviewMutation.isPending}
                onClick={(e) => {
                  e.preventDefault()
                  if (!rejectionReason.trim()) {
                    setErrorText('Vui lòng nhập lý do từ chối.')
                    return
                  }
                  handleReview('rejected')(e)
                }}
                variant="danger"
              >
                Từ chối
              </Button>
            </div>
          </form>

          <div style={{ marginTop: '1rem' }} />
          <Textarea
            label="Lý do từ chối (Bắt buộc nếu Từ chối)"
            name="rejection_reason"
            onChange={(e) => {
              setRejectionReason(e.target.value)
              if (e.target.value.trim()) setErrorText('')
            }}
            placeholder="Nhập lý do từ chối đơn xin nghỉ phép..."
            value={rejectionReason}
          />
        </div>
      </section>
    </div>
  )
}
