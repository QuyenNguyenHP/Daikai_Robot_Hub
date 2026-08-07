import { useCallback, useState } from 'react'
import { waitForRobotCamera } from '../services/camera'
import { useBrowserCamera } from './useBrowserCamera'


export function useCameraSource(videoRef, initialSource = 'webcam') {
  const {
    cameraOn: browserOn,
    error: browserError,
    setError: setBrowserError,
    startCamera: startBrowserCamera,
    stopCamera: stopBrowserCamera,
  } = useBrowserCamera(videoRef)
  const [source, setSource] = useState(initialSource)
  const [robotOn, setRobotOn] = useState(false)
  const [starting, setStarting] = useState(false)
  const [sourceError, setSourceError] = useState('')

  const cameraOn = source === 'webcam' ? browserOn : robotOn

  const stopCamera = useCallback(() => {
    if (source === 'webcam') stopBrowserCamera()
    else setRobotOn(false)
  }, [source, stopBrowserCamera])

  const startCamera = useCallback(async () => {
    setStarting(true)
    setSourceError('')
    setBrowserError('')
    try {
      if (source === 'webcam') await startBrowserCamera()
      else {
        await waitForRobotCamera()
        setRobotOn(true)
      }
      return true
    } catch (error) {
      setSourceError(error.message || 'Could not start the selected camera.')
      return false
    } finally {
      setStarting(false)
    }
  }, [setBrowserError, source, startBrowserCamera])

  const changeSource = useCallback((nextSource) => {
    stopBrowserCamera()
    setBrowserError('')
    setRobotOn(false)
    setSourceError('')
    setSource(nextSource)
  }, [setBrowserError, stopBrowserCamera])

  const clearError = useCallback(() => {
    setSourceError('')
    setBrowserError('')
  }, [setBrowserError])

  return {
    source,
    cameraOn,
    starting,
    error: sourceError || browserError,
    startCamera,
    stopCamera,
    changeSource,
    clearError,
  }
}
