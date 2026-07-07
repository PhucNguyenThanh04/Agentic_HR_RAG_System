import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { StatusMessage } from '@/components/ui/StatusMessage'
import { useDepartments } from '@/features/departments/hooks/useDepartments'
import { OnboardingCameraPanel } from '@/features/employee-onboarding/components/OnboardingCameraPanel'
import { useCancelOnboardingSession } from '@/features/employee-onboarding/hooks/useCancelOnboardingSession'
import { useCommitOnboardingSession } from '@/features/employee-onboarding/hooks/useCommitOnboardingSession'
import { useStartOnboardingSession } from '@/features/employee-onboarding/hooks/useStartOnboardingSession'
import { useUploadOnboardingImage } from '@/features/employee-onboarding/hooks/useUploadOnboardingImage'
import {
  onboardingSchema,
  type OnboardingFormInput,
  type OnboardingFormValues,
} from '@/features/employee-onboarding/schemas/onboarding.schema'
import type {
  OnboardingCommitResponse,
  OnboardingPhotoUploadResponse,
  OnboardingStartResponse,
} from '@/features/employee-onboarding/types/onboarding.types'
import { usePositions } from '@/features/positions/hooks/usePositions'
import { formatDateTime, getApiErrorMessage } from '@/lib/utils'

const REQUIRED_ONBOARDING_PHOTOS = 10

export function EmployeeOnboardingPage() {
  const [session, setSession] = useState<OnboardingStartResponse | null>(null)
  const [lastUpload, setLastUpload] = useState<OnboardingPhotoUploadResponse | null>(null)
  const [commitResult, setCommitResult] = useState<OnboardingCommitResponse | null>(null)
  const [acceptedPhotoCount, setAcceptedPhotoCount] = useState(0)
  const departmentsQuery = useDepartments()
  const positionsQuery = usePositions()
  const startSession = useStartOnboardingSession()
  const uploadImage = useUploadOnboardingImage()
  const commitSession = useCommitOnboardingSession()
  const cancelSession = useCancelOnboardingSession()
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useForm<OnboardingFormInput, unknown, OnboardingFormValues>({
    resolver: zodResolver(onboardingSchema),
    defaultValues: {
      department_id: 0,
      email: '',
      full_name: '',
      password: '',
      position_id: 0,
    },
  })

  const validPhotos = acceptedPhotoCount
  const readyToCommit = validPhotos >= REQUIRED_ONBOARDING_PHOTOS

  const onSubmit = (values: OnboardingFormValues) => {
    setCommitResult(null)
    setLastUpload(null)
    setAcceptedPhotoCount(0)
    startSession.mutate(values, {
      onSuccess: (response) => {
        setSession(response)
        setAcceptedPhotoCount(response.current_valid_photos)
      },
    })
  }

  const handleCameraCapture = async (file: File): Promise<OnboardingPhotoUploadResponse> => {
    if (!session) {
      throw new Error('Onboarding session is not ready')
    }

    const response = await uploadImage.mutateAsync({ file, sessionId: session.session_id })
    setLastUpload(response)
    setAcceptedPhotoCount(response.valid_photo_count)
    return response
  }

  const handleCommit = () => {
    if (!session) {
      return
    }

    commitSession.mutate(session.session_id, {
      onSuccess: (response) => {
        setCommitResult(response)
        setSession(null)
        setLastUpload(null)
        setAcceptedPhotoCount(0)
        reset()
      },
    })
  }

  const handleCancel = () => {
    if (!session) {
      return
    }

    cancelSession.mutate(session.session_id, {
      onSuccess: () => {
        setSession(null)
        setLastUpload(null)
        setCommitResult(null)
        setAcceptedPhotoCount(0)
      },
    })
  }

  return (
    <section className="page-grid">
      <div className="page-stack">
        <PageHeader
          description="Tạo user, employee và face profile thông qua /employee-onboarding."
          eyebrow="Enrollment"
          title="Onboarding nhân viên"
        />
        <form className="form-card" onSubmit={handleSubmit(onSubmit)}>
          <div className="form-grid">
            <Input error={errors.email?.message} label="Email" type="email" {...register('email')} />
            <Input
              error={errors.password?.message}
              label="Mật khẩu"
              type="password"
              {...register('password')}
            />
            <Input error={errors.full_name?.message} label="Họ tên" {...register('full_name')} />
            <Select error={errors.department_id?.message} label="Phòng ban" {...register('department_id')}>
              <option value={0}>Chọn phòng ban</option>
              {(departmentsQuery.data ?? []).map((department) => (
                <option key={department.department_id} value={department.department_id}>
                  {department.name}
                </option>
              ))}
            </Select>
            <Select error={errors.position_id?.message} label="Chức vụ" {...register('position_id')}>
              <option value={0}>Chọn chức vụ</option>
              {(positionsQuery.data ?? []).map((position) => (
                <option key={position.position_id} value={position.position_id}>
                  {position.name}
                </option>
              ))}
            </Select>
          </div>
          {startSession.isError ? (
            <StatusMessage tone="error">
              {getApiErrorMessage(startSession.error, 'Không thể tạo onboarding session.')}
            </StatusMessage>
          ) : null}
          <Button isLoading={startSession.isPending} type="submit">
            Bắt đầu session
          </Button>
        </form>
        {session ? (
          <div className="form-card">
            <div className="session-summary">
              <div>
                <span>Session</span>
                <strong>{session.session_id}</strong>
              </div>
              <div>
                <span>Hết hạn</span>
                <strong>{formatDateTime(session.expires_at)}</strong>
              </div>
              <div>
                <span>Ảnh hợp lệ</span>
                <strong>
                  {validPhotos}/{REQUIRED_ONBOARDING_PHOTOS}
                </strong>
              </div>
            </div>
            <OnboardingCameraPanel
              acceptedCount={validPhotos}
              disabled={uploadImage.isPending || commitSession.isPending}
              onCapture={handleCameraCapture}
              requiredCount={REQUIRED_ONBOARDING_PHOTOS}
            />
            {lastUpload ? (
              <StatusMessage tone={lastUpload.accepted ? 'success' : 'warning'}>
                {lastUpload.accepted ? 'Ảnh được chấp nhận.' : lastUpload.reason ?? 'Ảnh chưa đạt yêu cầu.'}
              </StatusMessage>
            ) : null}
            {uploadImage.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(uploadImage.error, 'Không thể upload ảnh onboarding.')}
              </StatusMessage>
            ) : null}
            {commitSession.isError ? (
              <StatusMessage tone="error">
                {getApiErrorMessage(commitSession.error, 'Không thể commit onboarding session.')}
              </StatusMessage>
            ) : null}
            <div className="action-row">
              <Button
                disabled={!readyToCommit}
                isLoading={commitSession.isPending}
                onClick={handleCommit}
              >
                Hoàn tất đăng ký
              </Button>
              <Button
                isLoading={cancelSession.isPending}
                onClick={handleCancel}
                variant="secondary"
              >
                Hủy session
              </Button>
            </div>
          </div>
        ) : null}
      </div>
      <aside className="side-panel">
        <h2>Kết quả</h2>
        {commitResult ? (
          <div className="result-list">
            <div>
              <span>Mã nhân viên</span>
              <strong>{commitResult.employee_code}</strong>
            </div>
            <div>
              <span>Employee ID</span>
              <strong>{commitResult.employee_id}</strong>
            </div>
            <div>
              <span>Face profile</span>
              <strong>{commitResult.face_profile_id ?? '-'}</strong>
            </div>
            <div>
              <span>Vectors</span>
              <strong>{commitResult.vectors_stored ?? '-'}</strong>
            </div>
          </div>
        ) : (
          <StatusMessage>
            Kết quả commit sẽ hiển thị sau khi session đủ ảnh hợp lệ.
          </StatusMessage>
        )}
      </aside>
    </section>
  )
}
