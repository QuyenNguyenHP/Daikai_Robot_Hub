import { useCallback, useEffect, useRef, useState } from 'react'
import {
  connectRobotCamera,
  enrollPerson,
  getHealth,
  getPeople,
  getRobotSnapshot,
  getRobotStatus,
  getRobotStreamUrl,
  recognizeImage,
  recognizeRobotFrame,
} from './api'

function captureFrame(video, maxWidth = 640, quality = 0.8) {
  if (!video?.videoWidth) return Promise.resolve(null)

  const width = Math.min(video.videoWidth, maxWidth)
  const height = Math.round((width * video.videoHeight) / video.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  canvas.getContext('2d').drawImage(video, 0, 0, width, height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
}

function boxIou(first, second) {
  const left = Math.max(first.x, second.x)
  const top = Math.max(first.y, second.y)
  const right = Math.min(first.x + first.width, second.x + second.width)
  const bottom = Math.min(first.y + first.height, second.y + second.height)
  const intersection = Math.max(right - left, 0) * Math.max(bottom - top, 0)
  const union = first.width * first.height + second.width * second.height - intersection
  return union > 0 ? intersection / union : 0
}

function smoothDetections(previous, current, alpha = 0.45) {
  const availablePrevious = new Set(previous.map((_, index) => index))

  return current.map((detection) => {
    let bestIndex = -1
    let bestIou = 0.2

    availablePrevious.forEach((index) => {
      const score = boxIou(previous[index].box, detection.box)
      if (score > bestIou) {
        bestIou = score
        bestIndex = index
      }
    })

    if (bestIndex === -1) return detection
    availablePrevious.delete(bestIndex)
    const oldDetection = previous[bestIndex]
    const oldBox = oldDetection.box
    const newBox = detection.box

    return {
      ...detection,
      confidence: oldDetection.name === detection.name
        ? oldDetection.confidence + alpha * (detection.confidence - oldDetection.confidence)
        : detection.confidence,
      box: {
        x: oldBox.x + alpha * (newBox.x - oldBox.x),
        y: oldBox.y + alpha * (newBox.y - oldBox.y),
        width: oldBox.width + alpha * (newBox.width - oldBox.width),
        height: oldBox.height + alpha * (newBox.height - oldBox.height),
      },
    }
  })
}

function useCamera(videoRef) {
  const streamRef = useRef(null)
  const [cameraOn, setCameraOn] = useState(false)
  const [cameraError, setCameraError] = useState('')

  const startCamera = useCallback(async () => {
    try {
      setCameraError('')
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      videoRef.current.srcObject = stream
      await videoRef.current.play()
      setCameraOn(true)
    } catch (error) {
      setCameraError(error.message || 'Camera permission was denied.')
    }
  }, [videoRef])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraOn(false)
  }, [videoRef])

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), [])
  return { cameraOn, cameraError, startCamera, stopCamera }
}

async function waitForRobotCamera() {
  await connectRobotCamera()
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const status = await getRobotStatus()
    if (status.connected) return
    if (status.state === 'error') throw new Error(status.error || 'Robot camera failed.')
    await new Promise((resolve) => window.setTimeout(resolve, 250))
  }
  throw new Error('Timed out waiting for the robot camera.')
}

function SourceSelector({ value, onChange, disabled = false }) {
  return (
    <label className="source-picker">
      <span>Camera source</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled}>
        <option value="webcam">Device webcam</option>
        <option value="robot">Unitree R1 camera</option>
      </select>
    </label>
  )
}

function CameraStage({ videoRef, detections = [], cameraOn = false, source = 'webcam' }) {
  return (
    <div className="camera-stage">
      {source === 'webcam' && <video ref={videoRef} muted playsInline />}
      {source === 'robot' && cameraOn && (
        <img src={getRobotStreamUrl()} alt="Live stream from the Unitree R1 camera" />
      )}
      <div className="scanline" />
      {detections.map((item, index) => (
        <div
          className={`face-box ${item.name === 'unknown' ? 'unknown' : ''}`}
          key={`${item.name}-${index}`}
          style={{
            left: `${(item.box.x / item.imageWidth) * 100}%`,
            top: `${(item.box.y / item.imageHeight) * 100}%`,
            width: `${(item.box.width / item.imageWidth) * 100}%`,
            height: `${(item.box.height / item.imageHeight) * 100}%`,
          }}
        >
          <span>{item.name} · {Math.round(item.confidence * 100)}%</span>
        </div>
      ))}
      {!cameraOn && (
        <div className="camera-placeholder">
          <div className="camera-icon">⌾</div>
          <strong>Camera is offline</strong>
          <span>Start the selected camera to begin</span>
        </div>
      )}
    </div>
  )
}

function RecognitionView() {
  const videoRef = useRef(null)
  const requestBusy = useRef(false)
  const [source, setSource] = useState('webcam')
  const [robotOn, setRobotOn] = useState(false)
  const [startingCamera, setStartingCamera] = useState(false)
  const [running, setRunning] = useState(false)
  const [threshold, setThreshold] = useState(0.45)
  const [detections, setDetections] = useState([])
  const [lastScan, setLastScan] = useState(null)
  const [error, setError] = useState('')
  const { cameraOn, cameraError, startCamera, stopCamera } = useCamera(videoRef)
  const selectedCameraOn = source === 'webcam' ? cameraOn : robotOn

  useEffect(() => {
    if (!running || !selectedCameraOn) return undefined
    const scan = async () => {
      if (requestBusy.current) return
      requestBusy.current = true
      try {
        let result
        if (source === 'webcam') {
          const blob = await captureFrame(videoRef.current)
          if (!blob) return
          result = await recognizeImage(blob, threshold)
        } else {
          result = await recognizeRobotFrame(threshold)
        }
        const currentDetections = result.detections.map((item) => ({
          ...item,
          imageWidth: result.image.width,
          imageHeight: result.image.height,
        }))
        setDetections((previous) => smoothDetections(previous, currentDetections))
        setLastScan(new Date())
        setError('')
      } catch (scanError) {
        setError(scanError.message)
      } finally {
        requestBusy.current = false
      }
    }
    scan()
    const timer = window.setInterval(scan, 300)
    return () => window.clearInterval(timer)
  }, [running, selectedCameraOn, source, threshold])

  const toggleCamera = async () => {
    if (selectedCameraOn) {
      setRunning(false)
      setDetections([])
      if (source === 'webcam') stopCamera()
      else setRobotOn(false)
      return
    }

    setStartingCamera(true)
    setError('')
    try {
      if (source === 'webcam') await startCamera()
      else {
        await waitForRobotCamera()
        setRobotOn(true)
      }
    } catch (startError) {
      setError(startError.message)
    } finally {
      setStartingCamera(false)
    }
  }

  const changeSource = (nextSource) => {
    setRunning(false)
    setDetections([])
    if (cameraOn) stopCamera()
    setRobotOn(false)
    setSource(nextSource)
    setError('')
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
        <SourceSelector value={source} onChange={changeSource} disabled={startingCamera} />
        <CameraStage videoRef={videoRef} detections={detections} cameraOn={selectedCameraOn} source={source} />
        <div className="camera-actions">
          <button className="button secondary" onClick={toggleCamera} disabled={startingCamera}>
            {startingCamera ? 'Connecting…' : selectedCameraOn ? 'Stop camera' : 'Start camera'}
          </button>
          <button
            className="button primary"
            disabled={!selectedCameraOn}
            onClick={() => setRunning((value) => !value)}
          >
            {running ? 'Pause recognition' : 'Start recognition'}
          </button>
        </div>
        {(error || cameraError) && <p className="error-message">{error || cameraError}</p>}
      </div>

      <aside className="side-stack">
        <div className="panel metric-panel">
          <p className="eyebrow">CURRENT FRAME</p>
          <div className="metric-row">
            <div><strong>{detections.length}</strong><span>faces</span></div>
            <div><strong>{detections.filter((d) => d.name !== 'unknown').length}</strong><span>recognized</span></div>
          </div>
          <div className="detection-list">
            {detections.length === 0 && <p className="muted">No faces in the latest frame.</p>}
            {detections.map((item, index) => (
              <div className="detection-item" key={`${item.name}-result-${index}`}>
                <div className="avatar">{item.name === 'unknown' ? '?' : item.name[0].toUpperCase()}</div>
                <div><strong>{item.name}</strong><span>Similarity {item.confidence.toFixed(3)}</span></div>
              </div>
            ))}
          </div>
        </div>
        <div className="panel control-panel">
          <div className="range-label"><span>Match threshold</span><strong>{threshold.toFixed(2)}</strong></div>
          <input type="range" min="0.3" max="0.7" step="0.01" value={threshold} onChange={(event) => setThreshold(Number(event.target.value))} />
          <p className="muted">Raise it to reduce false matches. Default: 0.45.</p>
          <div className="last-scan">Last response <strong>{lastScan ? lastScan.toLocaleTimeString() : '—'}</strong></div>
        </div>
      </aside>
    </section>
  )
}

function EnrollmentView({ onEnrolled }) {
  const videoRef = useRef(null)
  const filesRef = useRef([])
  const [source, setSource] = useState('webcam')
  const [robotOn, setRobotOn] = useState(false)
  const [startingCamera, setStartingCamera] = useState(false)
  const [captureError, setCaptureError] = useState('')
  const [name, setName] = useState('')
  const [files, setFiles] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState(null)
  const { cameraOn, cameraError, startCamera, stopCamera } = useCamera(videoRef)
  const selectedCameraOn = source === 'webcam' ? cameraOn : robotOn

  useEffect(() => { filesRef.current = files }, [files])
  useEffect(() => () => filesRef.current.forEach((item) => URL.revokeObjectURL(item.preview)), [])

  const addFiles = (newFiles) => {
    const additions = Array.from(newFiles).slice(0, Math.max(30 - files.length, 0)).map((file) => ({
      file,
      preview: URL.createObjectURL(file),
    }))
    setFiles((current) => [...current, ...additions])
  }

  const takePhoto = async () => {
    try {
      const blob = source === 'webcam'
        ? await captureFrame(videoRef.current, 1280, 0.9)
        : await getRobotSnapshot()
      if (!blob || files.length >= 30) return
      const file = new File([blob], `${source}-${Date.now()}.jpg`, { type: 'image/jpeg' })
      addFiles([file])
      setCaptureError('')
    } catch (photoError) {
      setCaptureError(photoError.message)
    }
  }

  const toggleCamera = async () => {
    if (selectedCameraOn) {
      if (source === 'webcam') stopCamera()
      else setRobotOn(false)
      return
    }

    setStartingCamera(true)
    setCaptureError('')
    try {
      if (source === 'webcam') await startCamera()
      else {
        await waitForRobotCamera()
        setRobotOn(true)
      }
    } catch (startError) {
      setCaptureError(startError.message)
    } finally {
      setStartingCamera(false)
    }
  }

  const changeSource = (nextSource) => {
    if (cameraOn) stopCamera()
    setRobotOn(false)
    setSource(nextSource)
    setCaptureError('')
  }

  const removePhoto = (index) => {
    setFiles((current) => {
      URL.revokeObjectURL(current[index].preview)
      return current.filter((_, itemIndex) => itemIndex !== index)
    })
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!name.trim() || files.length === 0) return
    setSubmitting(true)
    setMessage(null)
    try {
      const result = await enrollPerson(name, files.map((item) => item.file))
      setMessage({ type: 'success', text: `Saved ${result.accepted} valid samples for ${result.name}. ${result.rejected.length} rejected.` })
      files.forEach((item) => URL.revokeObjectURL(item.preview))
      setFiles([])
      setName('')
      onEnrolled()
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="enroll-grid">
      <form className="panel enroll-form" onSubmit={submit}>
        <div className="panel-heading">
          <div><p className="eyebrow">NEW IDENTITY</p><h2>Enroll a person</h2></div>
          <span className="sample-count">{files.length}/30 samples</span>
        </div>
        <label className="field-label" htmlFor="person-name">Person name</label>
        <input id="person-name" className="text-input" value={name} onChange={(event) => setName(event.target.value)} placeholder="e.g. Mit" maxLength="80" />

        <div className="upload-zone">
          <input id="photo-upload" type="file" accept="image/*" multiple onChange={(event) => addFiles(event.target.files)} />
          <label htmlFor="photo-upload"><strong>Choose photos</strong><span>JPG, PNG or WebP · up to 30 files · 10 MB each</span></label>
        </div>

        <div className="thumb-grid">
          {files.map((item, index) => (
            <button type="button" className="thumb" key={item.preview} onClick={() => removePhoto(index)} title="Remove photo">
              <img src={item.preview} alt={`Sample ${index + 1}`} /><span>×</span>
            </button>
          ))}
        </div>
        {message && <p className={message.type === 'error' ? 'error-message' : 'success-message'}>{message.text}</p>}
        <button className="button primary full" disabled={submitting || !name.trim() || files.length === 0}>
          {submitting ? 'Processing faces…' : 'Create face profile'}
        </button>
      </form>

      <div className="panel capture-panel">
        <div className="panel-heading"><div><p className="eyebrow">CAMERA SAMPLES</p><h2>Capture photos</h2></div></div>
        <SourceSelector value={source} onChange={changeSource} disabled={startingCamera} />
        <CameraStage videoRef={videoRef} cameraOn={selectedCameraOn} source={source} />
        <div className="camera-actions">
          <button className="button secondary" type="button" disabled={startingCamera} onClick={toggleCamera}>
            {startingCamera ? 'Connecting…' : selectedCameraOn ? 'Stop camera' : 'Start camera'}
          </button>
          <button className="button primary" type="button" disabled={!selectedCameraOn || files.length >= 30} onClick={takePhoto}>Capture sample</button>
        </div>
        {(captureError || cameraError) && <p className="error-message">{captureError || cameraError}</p>}
        <div className="tips"><strong>For better recognition</strong><span>Use 10–20 clear photos with small changes in angle, distance and expression. Keep one face per photo.</span></div>
      </div>
    </section>
  )
}

function PeopleView({ people, loading }) {
  return (
    <section className="panel people-panel">
      <div className="panel-heading"><div><p className="eyebrow">FACE DATABASE</p><h2>Enrolled people</h2></div><span className="sample-count">{people.length} profiles</span></div>
      {loading && <p className="muted">Loading database…</p>}
      {!loading && people.length === 0 && <div className="empty-state"><strong>No people enrolled</strong><span>Create a profile from the Enroll screen.</span></div>}
      <div className="people-list">
        {people.map((person) => (
          <div className="person-row" key={person.name}>
            <div className="avatar large">{person.name[0].toUpperCase()}</div>
            <div className="person-name"><strong>{person.name}</strong><span>Updated {person.updated_at ? new Date(person.updated_at).toLocaleString() : 'unknown'}</span></div>
            <div><strong>{person.samples}</strong><span>latest samples</span></div>
            <div><strong>{person.stored_photos}</strong><span>stored photos</span></div>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function App() {
  const [view, setView] = useState('recognize')
  const [health, setHealth] = useState(null)
  const [people, setPeople] = useState([])
  const [loadingPeople, setLoadingPeople] = useState(true)
  const [connectionError, setConnectionError] = useState('')

  const refresh = useCallback(async () => {
    setLoadingPeople(true)
    try {
      const [healthResult, peopleResult] = await Promise.all([getHealth(), getPeople()])
      setHealth(healthResult)
      setPeople(peopleResult.people)
      setConnectionError('')
    } catch (error) {
      setConnectionError(error.message)
    } finally {
      setLoadingPeople(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setView('recognize')}><span className="brand-mark">FL</span><span>FaceLens<small>Recognition console</small></span></button>
        <nav>
          <button className={view === 'recognize' ? 'active' : ''} onClick={() => setView('recognize')}>Recognize</button>
          <button className={view === 'enroll' ? 'active' : ''} onClick={() => setView('enroll')}>Enroll</button>
          <button className={view === 'people' ? 'active' : ''} onClick={() => setView('people')}>People</button>
        </nav>
        <div className={`api-status ${health ? 'online' : ''}`}><i />{health ? `API online · ${health.people_count} people` : 'API offline'}</div>
      </header>
      <main>
        <div className="page-intro">
          <div><p className="eyebrow">YUNET + SFACE</p><h1>{view === 'recognize' ? 'See who is there.' : view === 'enroll' ? 'Teach the system a new face.' : 'Your recognition database.'}</h1></div>
          <p>Local face detection and recognition powered by your existing OpenCV models.</p>
        </div>
        {connectionError && <div className="connection-banner">Cannot reach the FastAPI backend: {connectionError}</div>}
        {view === 'recognize' && <RecognitionView />}
        {view === 'enroll' && <EnrollmentView onEnrolled={refresh} />}
        {view === 'people' && <PeopleView people={people} loading={loadingPeople} />}
      </main>
      <footer>FaceLens MVP · Images and embeddings stay on this machine</footer>
    </div>
  )
}
