import { Table } from '@/components/ui/Table'
import { FaceProfileStatusBadge } from '@/features/face-profiles/components/FaceProfileStatusBadge'
import type { FaceProfile } from '@/features/face-profiles/types/face-profile.types'
import { useRevokeFaceProfile } from '@/features/face-profiles/hooks/useRevokeFaceProfile'
import { formatDateTime } from '@/lib/utils'

type FaceProfileTableProps = {
  profiles: FaceProfile[]
  employeeNames: Map<string, string>
}

export function FaceProfileTable({ profiles, employeeNames }: FaceProfileTableProps) {
  const revokeProfile = useRevokeFaceProfile()

  const handleRevoke = (profileId: string) => {
    const reason = window.prompt('Nhập lý do thu hồi vector khuôn mặt này (tối thiểu 3 ký tự):')
    if (reason === null) return // Cancelled
    if (reason.trim().length < 3) {
      window.alert('Lý do thu hồi quá ngắn.')
      return
    }

    revokeProfile.mutate(
      { profileId, reason: reason.trim() },
      {
        onSuccess: () => {
          window.alert('Thu hồi thành công!')
        },
        onError: (err) => {
          window.alert(`Thu hồi thất bại: ${err instanceof Error ? err.message : 'Lỗi không xác định'}`)
        },
      }
    )
  }

  return (
    <Table>
      <thead>
        <tr>
          <th>Profile ID</th>
          <th>Nhân viên</th>
          <th>Collection</th>
          <th>Model</th>
          <th>Trạng thái</th>
          <th>Cập nhật</th>
          <th>Chi tiết / Hành động</th>
        </tr>
      </thead>
      <tbody>
        {profiles.map((profile) => {
          const empName = employeeNames.get(profile.employee_id)
          return (
            <tr key={profile.profile_id}>
              <td className="mono-cell" title={profile.profile_id}>
                {profile.profile_id.slice(0, 8)}...
              </td>
              <td>
                {empName ? (
                  <strong>{empName}</strong>
                ) : (
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {profile.employee_id.slice(0, 8)}...
                  </span>
                )}
              </td>
              <td>{profile.qdrant_collection}</td>
              <td>
                {profile.embedding_model ? (
                  <div>
                    <div>{profile.embedding_model}</div>
                    {profile.embedding_version && (
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        v{profile.embedding_version}
                      </div>
                    )}
                  </div>
                ) : (
                  '-'
                )}
              </td>
              <td>
                <FaceProfileStatusBadge status={profile.status} />
              </td>
              <td>{formatDateTime(profile.updated_at)}</td>
              <td>
                {profile.status === 'active' ? (
                  <button
                    className="button button--secondary button--sm"
                    style={{ color: 'var(--status-error)' }}
                    onClick={() => handleRevoke(profile.profile_id)}
                    disabled={revokeProfile.isPending}
                  >
                    Thu hồi
                  </button>
                ) : profile.status === 'revoked' ? (
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Lý do: {profile.revocation_reason || '-'}
                  </div>
                ) : (
                  '-'
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}
