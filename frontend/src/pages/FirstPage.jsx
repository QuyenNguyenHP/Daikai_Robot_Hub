import { useCallback, useEffect, useRef, useState } from 'react'
import { CameraSourceSelector } from '../components/CameraSourceSelector'
import { CameraStage } from '../components/CameraStage'
import { DetectionSummary } from '../components/DetectionSummary'
import { RobotSpeechPanel } from '../components/RobotSpeechPanel'
import { ThresholdControl } from '../components/ThresholdControl'
import { useCameraSource } from '../hooks/useCameraSource'
import {
  recognizeRobotFrame,
  recognizeWebcamFrame,
  speakOnRobot,
} from '../services/api'
import { captureVideoFrame } from '../services/camera'
import { addImageDimensions, smoothDetections } from '../services/detections'


const AUTO_SPEECH_CONFIDENCE = 0.7
const ANNOUNCEMENT_COOLDOWN_MS = 15_000


export function FirstPage() {
  const videoRef = useRef(null)
  const recognitionBusy = useRef(false)
  const speechRequestBusy = useRef(false)
  const announcementTimes = useRef(new Map())
  const camera = useCameraSource(videoRef)
  const [running, setRunning] = useState(false)
  const [threshold, setThreshold] = useState(0.45)
  const [detections, setDetections] = useState([])
  const [lastScan, setLastScan] = useState(null)
  const [scanError, setScanError] = useState('')
  const [autoSpeechEnabled, setAutoSpeechEnabled] = useState(false)
  const [speechBusy, setSpeechBusy] = useState(false)
  const [speechMessage, setSpeechMessage] = useState(null)
  const [lastSpoken, setLastSpoken] = useState('')

  const speak = useCallback(async (text, automatic = false) => {
    const normalized = text.trim()
    if (!normalized || speechRequestBusy.current) return false
    speechRequestBusy.current = true
    setSpeechBusy(true)
    setSpeechMessage(null)
    try {
      const result = await speakOnRobot(normalized)
      setLastSpoken(result.text)
      setSpeechMessage({
        type: 'success',
        text: automatic ? `Automatically announced ${result.text}.` : 'Speech completed.',
      })
      return true
    } catch (error) {
      setSpeechMessage({ type: 'error', text: error.message })
      return false
    } finally {
      speechRequestBusy.current = false
      setSpeechBusy(false)
    }
  }, [])

  const announceBestDetection = useCallback((current) => {
    if (!autoSpeechEnabled || speechRequestBusy.current) return
    const best = current
      .filter(({ name, confidence }) => (
        name !== 'unknown' && confidence >= AUTO_SPEECH_CONFIDENCE
      ))
      .sort((first, second) => second.confidence - first.confidence)[0]
    if (!best) return

    const now = Date.now()
    const previousTime = announcementTimes.current.get(best.name) || 0
    if (now - previousTime < ANNOUNCEMENT_COOLDOWN_MS) return

    announcementTimes.current.set(best.name, now)
    void speak(`Hello, ${best.name}.`, true)
  }, [autoSpeechEnabled, speak])

  useEffect(() => {
    if (!running || !camera.cameraOn) return undefined
    let active = true

    const scan = async () => {
      if (recognitionBusy.current) return
      recognitionBusy.current = true
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
        announceBestDetection(current)
      } catch (error) {
        if (active) setScanError(error.message)
      } finally {
        recognitionBusy.current = false
      }
    }

    scan()
    const timer = window.setInterval(scan, 300)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [
    announceBestDetection,
    camera.cameraOn,
    camera.source,
    running,
    threshold,
  ])

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

  const toggleAutoSpeech = () => {
    setAutoSpeechEnabled((enabled) => !enabled)
    announcementTimes.current.clear()
    setSpeechMessage(null)
  }

  return (
    <div className="first-page">
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
              {camera.starting
                ? 'Connecting…'
                : camera.cameraOn ? 'Stop camera' : 'Start camera'}
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

      <RobotSpeechPanel
        autoEnabled={autoSpeechEnabled}
        busy={speechBusy}
        message={speechMessage}
        lastSpoken={lastSpoken}
        onSpeak={speak}
        onToggleAuto={toggleAutoSpeech}
      />
    </div>
  )
}
