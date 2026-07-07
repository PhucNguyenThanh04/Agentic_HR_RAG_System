import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { StatusMessage } from '@/components/ui/StatusMessage'
import type { OnboardingPhotoUploadResponse } from '@/features/employee-onboarding/types/onboarding.types'

const RETINAFACE_INPUT_SIZE = 640
const CAMERA_CONSTRAINTS: MediaStreamConstraints = {
  audio: false,
  video: {
    facingMode: 'user',
    height: { ideal: RETINAFACE_INPUT_SIZE },
    width: { ideal: RETINAFACE_INPUT_SIZE },
  },
}

type OnboardingCameraPanelProps = {
  acceptedCount: number
  disabled?: boolean
  onCapture: (file: File) => Promise<OnboardingPhotoUploadResponse>
  requiredCount: number
}

function stopMediaStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop())
}

function waitForVideoMetadata(video: HTMLVideoElement): Promise<void> {
  if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
    return Promise.resolve()
  }

  return new Promise((resolve) => {
    video.onloadedmetadata = () => resolve()
  })
}

export function OnboardingCameraPanel({
  acceptedCount,
  disabled = false,
  onCapture,
  requiredCount,
}: OnboardingCameraPanelProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [frameSize, setFrameSize] = useState<string | null>(null)
  const [isCameraOn, setIsCameraOn] = useState(false)
  const [isCapturing, setIsCapturing] = useState(false)

  useEffect(() => {
    return () => {
      stopMediaStream(streamRef.current)
    }
  }, [])

  const handleStartCamera = async () => {
    setCameraError(null)

    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS)

      streamRef.current = mediaStream

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
        await waitForVideoMetadata(videoRef.current)
        await videoRef.current.play()

        setFrameSize(`${videoRef.current.videoWidth} x ${videoRef.current.videoHeight}`)
      }

      setIsCameraOn(true)
    } catch {
      setFrameSize(null)
      setCameraError('Không thể bật camera. Kiểm tra quyền truy cập camera của trình duyệt.')
    }
  }

  const handleStopCamera = () => {
    stopMediaStream(streamRef.current)
    streamRef.current = null

    if (videoRef.current) {
      videoRef.current.srcObject = null
    }

    setIsCameraOn(false)
    setFrameSize(null)
  }

  const handleCapture = async () => {
    const video = videoRef.current
    const canvas = canvasRef.current

    if (!video || !canvas || !isCameraOn) {
      return
    }

    setIsCapturing(true)
    setCameraError(null)

    try {
      canvas.width = RETINAFACE_INPUT_SIZE
      canvas.height = RETINAFACE_INPUT_SIZE

      const context = canvas.getContext('2d')
      if (!context || video.videoWidth === 0 || video.videoHeight === 0) {
        throw new Error('Camera frame is not ready')
      }

      const sourceSize = Math.min(video.videoWidth, video.videoHeight)
      const sourceX = (video.videoWidth - sourceSize) / 2
      const sourceY = (video.videoHeight - sourceSize) / 2

      context.drawImage(
        video,
        sourceX,
        sourceY,
        sourceSize,
        sourceSize,
        0,
        0,
        RETINAFACE_INPUT_SIZE,
        RETINAFACE_INPUT_SIZE,
      )

      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(resolve, 'image/jpeg', 0.92)
      })

      if (!blob) {
        throw new Error('Cannot create image blob')
      }

      await onCapture(new File([blob], `face-${Date.now()}.jpg`, { type: 'image/jpeg' }))
    } catch {
      setCameraError('Không thể chụp ảnh từ camera.')
    } finally {
      setIsCapturing(false)
    }
  }

  const hasEnoughPhotos = acceptedCount >= requiredCount

  return (
    <div className="camera-panel">
      <div className="camera-panel__header">
        <div>
          <span>Stream camera</span>
          <strong>{frameSize ?? `${RETINAFACE_INPUT_SIZE} x ${RETINAFACE_INPUT_SIZE}`}</strong>
        </div>
        <div>
          <span>Ảnh gửi server</span>
          <strong>{RETINAFACE_INPUT_SIZE} x {RETINAFACE_INPUT_SIZE}</strong>
        </div>
        <div>
          <span>Ảnh hợp lệ</span>
          <strong>
            {acceptedCount}/{requiredCount}
          </strong>
        </div>
      </div>
      <div className="camera-preview">
        <video
          aria-label="Camera preview"
          autoPlay
          muted
          playsInline
          ref={videoRef}
        />
        {!isCameraOn ? <div className="camera-preview__placeholder">Camera đang tắt</div> : null}
      </div>
      <canvas ref={canvasRef} hidden />
      <div className="action-row">
        <Button
          disabled={disabled || isCameraOn}
          onClick={handleStartCamera}
          variant="secondary"
        >
          Bật camera
        </Button>
        <Button
          disabled={disabled || !isCameraOn || isCapturing}
          onClick={handleStopCamera}
          variant="secondary"
        >
          Tắt camera
        </Button>
        <Button
          disabled={disabled || !isCameraOn || isCapturing || hasEnoughPhotos}
          isLoading={isCapturing}
          onClick={handleCapture}
        >
          Chụp và gửi ảnh
        </Button>
      </div>
      {cameraError ? <StatusMessage tone="error">{cameraError}</StatusMessage> : null}
    </div>
  )
}
