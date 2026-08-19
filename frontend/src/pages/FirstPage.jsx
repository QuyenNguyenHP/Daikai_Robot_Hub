import { useCallback, useEffect, useRef, useState } from 'react'
import { BatteryStatus } from '../components/BatteryStatus'
import { CameraStage } from '../components/CameraStage'
import { RobotSpeechPanel } from '../components/RobotSpeechPanel'
import { RobotControlPanel } from '../components/RobotControlPanel'
import { RobotUpperBodyControl } from '../components/robot_upper_body_control'
import { RobotLedPanel } from '../components/RobotLedPanel'
import { useCameraSource } from '../hooks/useCameraSource'
import {
  recognizeRobotFrame,
  speakOnRobot,
} from '../services/api'
import { addImageDimensions, smoothDetections } from '../services/detections'


const AUTO_SPEECH_CONFIDENCE = 0.55
const ANNOUNCEMENT_COOLDOWN_MS = 15_000
// Leave the Jetson a short idle window after each inference. The effective
// recognition period is the request latency plus this cooldown.
const RECOGNITION_COOLDOWN_MS = 700


function formatNames(names) {
  if (names.length === 1) return names[0]
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  return `${names.slice(0, -1).join(', ')}, and ${names.at(-1)}`
}


export function FirstPage() {
  const videoRef = useRef(null)
  const recognitionBusy = useRef(false)
  const speechRequestBusy = useRef(false)
  const announcementTimes = useRef(new Map())
  const camera = useCameraSource(videoRef, 'robot')
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

  const announceDetections = useCallback((current) => {
    if (!autoSpeechEnabled || speechRequestBusy.current) return
    const recognizedByName = new Map()
    current
      .filter(({ name, confidence }) => (
        name !== 'unknown' && confidence >= AUTO_SPEECH_CONFIDENCE
      ))
      .forEach((detection) => {
        const previous = recognizedByName.get(detection.name)
        if (!previous || detection.confidence > previous.confidence) {
          recognizedByName.set(detection.name, detection)
        }
      })

    const now = Date.now()
    const names = [...recognizedByName.values()]
      .filter(({ name }) => (
        now - (announcementTimes.current.get(name) || 0) >= ANNOUNCEMENT_COOLDOWN_MS
      ))
      .sort((first, second) => second.confidence - first.confidence)
      .map(({ name }) => name)
    if (names.length === 0) return

    names.forEach((name) => announcementTimes.current.set(name, now))
    const greeting = new Date(now).getHours() < 12
      ? 'Good morning'
      : 'Good afternoon'
    void speak(`${greeting}, ${formatNames(names)}.`, true)
  }, [autoSpeechEnabled, speak])

  useEffect(() => {
    if (!running || !camera.cameraOn) return undefined
    let active = true
    let timer = null

    const scan = async () => {
      if (!recognitionBusy.current) {
        recognitionBusy.current = true
        try {
          const result = await recognizeRobotFrame(threshold)
          if (!active) return
          const current = addImageDimensions(result)
          setDetections((previous) => smoothDetections(previous, current))
          setLastScan(new Date())
          setScanError('')
          announceDetections(current)
        } catch (error) {
          if (active) setScanError(error.message)
        } finally {
          recognitionBusy.current = false
        }
      }

      if (active) timer = window.setTimeout(scan, RECOGNITION_COOLDOWN_MS)
    }

    void scan()
    return () => {
      active = false
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [
    announceDetections,
    camera.cameraOn,
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

  const toggleAutoSpeech = () => {
    setAutoSpeechEnabled((enabled) => !enabled)
    announcementTimes.current.clear()
    setSpeechMessage(null)
  }

  return (
    <div className="first-page">
      <section className="workspace-grid">
        <BatteryStatus />

        <div className="camera-column">
          <div className="panel camera-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">LIVE CAMERA</p>
              <h2>Face Recognition</h2>
            </div>
            <div className="camera-header-actions">
              <span className={`status-pill ${running ? 'live' : ''}`}>
                <i /> {running ? 'Scanning' : 'Standby'}
              </span>
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
          </div>
          {(scanError || camera.error) && (
            <p className="error-message camera-warning">
              {scanError || camera.error}
            </p>
          )}
          <CameraStage
            videoRef={videoRef}
            detections={detections}
            cameraOn={camera.cameraOn}
            source="robot"
            threshold={threshold}
            lastScan={lastScan}
            onThresholdChange={setThreshold}
          />
          </div>

          <div className="panel speech-panel">
            <RobotSpeechPanel
              autoEnabled={autoSpeechEnabled}
              busy={speechBusy}
              message={speechMessage}
              lastSpoken={lastSpoken}
              onSpeak={speak}
              onToggleAuto={toggleAutoSpeech}
            />
          </div>

          <RobotLedPanel />

          <div className="panel upper-body-panel">
            <RobotUpperBodyControl />
          </div>
        </div>

        <RobotControlPanel />
      </section>


    </div>
  )
}
