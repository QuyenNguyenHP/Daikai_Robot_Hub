import { useEffect, useRef, useState } from 'react'
import { CameraSourceSelector } from '../components/CameraSourceSelector'
import { CameraStage } from '../components/CameraStage'
import { DetectionSummary } from '../components/DetectionSummary'
import { ThresholdControl } from '../components/ThresholdControl'
import { useCameraSource } from '../hooks/useCameraSource'
import { recognizeRobotFrame, recognizeWebcamFrame } from '../services/api'
import { captureVideoFrame } from '../services/camera'
import { addImageDimensions, smoothDetections } from '../services/detections'


export function RecognitionPage() {
  const videoRef = useRef(null)
  const requestBusy = useRef(false)
  const camera = useCameraSource(videoRef)
  const [running, setRunning] = useState(false)
  const [threshold, setThreshold] = useState(0.45)
  const [detections, setDetections] = useState([])
  const [lastScan, setLastScan] = useState(null)
  const [scanError, setScanError] = useState('')

  useEffect(() => {
    if (!running || !camera.cameraOn) return undefined
    let active = true

    const scan = async () => {
      if (requestBusy.current) return
      requestBusy.current = true
      try {
        let result
        if (camera.source === 'webcam') {
          const blob = await captureVideoFrame(videoRef.current)
          if (!blob) return
          result = await recognizeWebcamFrame(blob, threshold)
        } else {
          result = await recognizeRobotFrame(threshold)
        }
        if (!active) return
        const current = addImageDimensions(result)
        setDetections((previous) => smoothDetections(previous, current))
        setLastScan(new Date())
        setScanError('')
      } catch (error) {
        if (active) setScanError(error.message)
      } finally {
        requestBusy.current = false
      }
    }

    scan()
    const timer = window.setInterval(scan, 300)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [running, camera.cameraOn, camera.source, threshold])

  const toggleCamera = async () => {
    if (camera.cameraOn) {
      setRunning(false)
      setDetections([])
      camera.stopCamera()
    } else {
      setScanError('')
      await camera.startCamera()
    }
  }

  const changeSource = (nextSource) => {
    setRunning(false)
    setDetections([])
    setScanError('')
    camera.changeSource(nextSource)
  }

  return (
    <section className="workspace-grid">
      <div className="panel camera-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">LIVE INPUT</p>
            <h2>Recognition stream</h2>
          </div>
          <span className={`status-pill ${running ? 'live' : ''}`}>
            <i /> {running ? 'Scanning' : 'Standby'}
          </span>
        </div>
        <CameraSourceSelector
          value={camera.source}
          onChange={changeSource}
          disabled={camera.starting}
        />
        <CameraStage
          videoRef={videoRef}
          detections={detections}
          cameraOn={camera.cameraOn}
          source={camera.source}
        />
        <div className="camera-actions">
          <button
            className="button secondary"
            onClick={toggleCamera}
            disabled={camera.starting}
          >
            {camera.starting ? 'Connecting…' : camera.cameraOn ? 'Stop camera' : 'Start camera'}
          </button>
          <button
            className="button primary"
            disabled={!camera.cameraOn}
            onClick={() => setRunning((value) => !value)}
          >
            {running ? 'Pause recognition' : 'Start recognition'}
          </button>
        </div>
        {(scanError || camera.error) && (
          <p className="error-message">{scanError || camera.error}</p>
        )}
      </div>

      <aside className="side-stack">
        <DetectionSummary detections={detections} />
        <ThresholdControl
          threshold={threshold}
          lastScan={lastScan}
          onChange={setThreshold}
        />
      </aside>
    </section>
  )
}
