import { useCallback, useEffect, useRef, useState } from 'react'


export function useBrowserCamera(videoRef) {
  const streamRef = useRef(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [error, setError] = useState('')

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
  }, [videoRef])

  const startCamera = useCallback(async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      })
      if (!videoRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        throw new Error('The webcam preview is not ready.')
      }
      streamRef.current = stream
      videoRef.current.srcObject = stream
      await videoRef.current.play()
      setCameraOn(true)
    } catch (cameraError) {
      setError(cameraError.message || 'Camera permission was denied.')
      throw cameraError
    }
  }, [videoRef])

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
  }, [])

  return { cameraOn, error, setError, startCamera, stopCamera }
}
