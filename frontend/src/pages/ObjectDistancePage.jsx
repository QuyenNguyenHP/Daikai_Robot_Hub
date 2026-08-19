import { useEffect, useRef, useState } from 'react'
import {
  getRobotStereoStatus,
  getRobotStereoStreamUrl,
  getRobotStereoWebSocketUrl,
  setRobotStereoClasses,
  startRobotStereo,
  stopRobotStereo,
} from '../services/api'


function Monitor({ title, view, running, streamVersion }) {
  return (
    <section className="panel stereo-monitor-panel">
      <div className="stereo-monitor-heading">
        <div>
          <h2>{title}</h2>
        </div>
        <span className={`status-pill ${running ? 'live' : ''}`}>
          <i /> {running ? 'Live' : 'Offline'}
        </span>
      </div>
      <div className="stereo-monitor">
        {running ? (
          <img
            src={getRobotStereoStreamUrl(view, streamVersion)}
            alt={`${title} live monitor`}
          />
        ) : (
          <div className="camera-placeholder">
            <div className="camera-icon">⌾</div>
            <strong>{title} is offline</strong>
            <span>Start stereo detection to open this monitor</span>
          </div>
        )}
      </div>
    </section>
  )
}


export function ObjectDistancePage() {
  const [status, setStatus] = useState(null)
  const [requestBusy, setRequestBusy] = useState(false)
  const [error, setError] = useState('')
  const [streamVersion, setStreamVersion] = useState(0)
  const [classText, setClassText] = useState('')
  const classesDirty = useRef(false)

  useEffect(() => {
    let active = true
    let socket = null
    let reconnectTimer = null
    let reconnectDelay = 1000

    const connect = () => {
      socket = new WebSocket(getRobotStereoWebSocketUrl())
      socket.onopen = () => {
        reconnectDelay = 1000
        if (active) setError('')
      }
      socket.onmessage = (event) => {
        if (!active) return
        try {
          const result = JSON.parse(event.data)
          setStatus(result)
          if (!classesDirty.current) {
            setClassText((result.classes || []).join(', '))
          }
        } catch {
          setError('The stereo status update could not be decoded.')
        }
      }
      socket.onclose = () => {
        if (!active) return
        setError('Stereo status connection lost. Reconnecting…')
        reconnectTimer = window.setTimeout(connect, reconnectDelay)
        reconnectDelay = Math.min(reconnectDelay * 2, 5000)
      }
    }

    connect()
    return () => {
      active = false
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer)
      if (socket && socket.readyState < WebSocket.CLOSING) socket.close()
    }
  }, [])

  const start = async () => {
    setRequestBusy(true)
    setError('')
    try {
      setStatus(await startRobotStereo())
      setStreamVersion((version) => version + 1)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRequestBusy(false)
    }
  }

  const stop = async () => {
    setRequestBusy(true)
    setError('')
    try {
      setStatus(await stopRobotStereo())
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRequestBusy(false)
    }
  }

  const updateClasses = async () => {
    const classes = classText
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .filter((item, index, values) => (
        values.findIndex((candidate) => candidate.toLowerCase() === item.toLowerCase()) === index
      ))
    if (classes.length === 0) {
      setError('Enter at least one object name, separated by commas.')
      return
    }

    setRequestBusy(true)
    setError('')
    const restart = running
    try {
      if (restart) await stopRobotStereo()
      const updated = await setRobotStereoClasses(classes)
      classesDirty.current = false
      setClassText((updated.classes || classes).join(', '))
      if (restart) {
        setStatus(await startRobotStereo())
        setStreamVersion((version) => version + 1)
      } else {
        setStatus(updated)
      }
    } catch (requestError) {
      setError(requestError.message)
      try {
        setStatus(await getRobotStereoStatus())
      } catch {
        // Keep the last status if the recovery request also fails.
      }
    } finally {
      setRequestBusy(false)
    }
  }

  const running = Boolean(status?.running)
  const connected = Boolean(status?.connected)
  const detections = status?.detections || []
  const stateLabel = status?.state === 'loading'
    ? 'Loading model…'
    : status?.state === 'waiting'
      ? 'Waiting for stereo video…'
      : connected ? 'Stereo connected' : 'Stereo stopped'

  return (
    <div className="object-distance-page">
      {status?.state === 'loading' && (
        <div className="model-loading-overlay" role="status" aria-live="polite">
          <div className="model-loading-content">
            <span className="model-loading-spinner" aria-hidden="true" />
            <strong>Loading YOLO-World model…</strong>
            <span>Preparing object prompts and stereo processing</span>
          </div>
        </div>
      )}
      <section className="stereo-page-heading">
        <div>
          <h1>Object detection and distance</h1>
          <p>
            YOLO-World detections with metric depth from the R1 left and right
            RTP cameras on UDP ports {status?.ports?.left || 5002} and{' '}
            {status?.ports?.right || 5003}.
          </p>
        </div>
        <div className="stereo-page-actions">
          <span className={`status-pill ${connected ? 'live' : ''}`}>
            <i /> {stateLabel}
          </span>
          {running ? (
            <button
              type="button"
              className="button secondary"
              disabled={requestBusy}
              onClick={stop}
            >
              {requestBusy ? 'Stopping…' : 'Stop detection'}
            </button>
          ) : (
            <button
              type="button"
              className="button primary"
              disabled={requestBusy || status?.configured === false}
              onClick={start}
            >
              {requestBusy ? 'Starting…' : 'Start detection'}
            </button>
          )}
        </div>
      </section>

      {(error || status?.error) && (
        <p className="error-message stereo-page-error">{error || status.error}</p>
      )}

      <section className="panel stereo-class-editor">
        <div>
          <h2>Objects to detect</h2>
          <p>Enter English object names separated by commas.</p>
        </div>
        <div className="stereo-class-controls">
          <input
            className="text-input"
            value={classText}
            onChange={(event) => {
              classesDirty.current = true
              setClassText(event.target.value)
            }}
            placeholder="person, chair, bottle, cup"
            aria-label="Objects to detect"
          />
          <button
            type="button"
            className="button primary"
            disabled={requestBusy || !classText.trim()}
            onClick={updateClasses}
          >
            {requestBusy ? 'Applying…' : 'Apply objects'}
          </button>
        </div>
      </section>

      <div className="stereo-monitor-grid">
        <Monitor
          title="Object detection"
          view="detection"
          running={running}
          streamVersion={streamVersion}
        />
        <Monitor
          title="Distance monitor"
          view="depth"
          running={running}
          streamVersion={streamVersion}
        />
      </div>

      <div className="stereo-details-grid">
        <section className="panel stereo-metrics-panel">
          <p className="eyebrow">PIPELINE METRICS</p>
          <div className="stereo-metrics">
            <div><strong>{status?.fps ?? '—'}</strong><span>FPS</span></div>
            <div><strong>{status?.stereo_ms ?? '—'}</strong><span>Stereo ms</span></div>
            <div><strong>{status?.yolo_ms ?? '—'}</strong><span>YOLO ms</span></div>
            <div><strong>{status?.pair_delta_ms ?? '—'}</strong><span>Pair delta ms</span></div>
          </div>
          <p className="stereo-config-detail">
            Baseline {status?.baseline_m ? `${status.baseline_m} m` : '—'} ·{' '}
            {status?.distance_mode === 'euclidean' ? 'Euclidean' : 'Optical-axis Z'} distance
          </p>
        </section>

        <section className="panel stereo-detections-panel">
          <div className="stereo-detections-heading">
            <div>
              <p className="eyebrow">CURRENT FRAME</p>
              <h2>Detected objects</h2>
            </div>
            <strong>{detections.length}</strong>
          </div>
          <div className="stereo-detection-list">
            {detections.length === 0 && (
              <p className="muted">No objects detected in the latest frame.</p>
            )}
            {detections.map((item, index) => (
              <div className="stereo-detection-row" key={`${item.name}-${index}`}>
                <span style={{ background: item.color || 'var(--cyan)' }}>
                  {item.name.slice(0, 1).toUpperCase()}
                </span>
                <div>
                  <strong>{item.name}</strong>
                  <small>{Math.round(item.confidence * 100)}% confidence</small>
                </div>
                <b>{item.distance_m === null ? 'No depth' : `${item.distance_m.toFixed(2)} m`}</b>
              </div>
            ))}
          </div>
        </section>
      </div>

      <p className="stereo-safety-note">
        Distance is a stereo perception estimate, not a safety-rated measurement.
        The stereo push service may conflict with the standard robot video service.
      </p>
    </div>
  )
}
