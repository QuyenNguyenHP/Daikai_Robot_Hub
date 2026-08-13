import { useCallback, useEffect, useRef, useState } from 'react'
import { getRobotStreamUrl } from '../services/api'


export function CameraStage({
  videoRef,
  detections = [],
  cameraOn = false,
  source = 'webcam',
  threshold,
  lastScan,
  onThresholdChange,
}) {
  const [streamVersion, setStreamVersion] = useState(0)
  const streamRetryTimer = useRef(null)
  const streamRetryDelay = useRef(1000)
  const showRecognitionDetails = (
    threshold !== undefined && typeof onThresholdChange === 'function'
  )
  const recognizedCount = detections.filter(({ name }) => name !== 'unknown').length

  useEffect(() => () => {
    if (streamRetryTimer.current !== null) {
      window.clearTimeout(streamRetryTimer.current)
    }
  }, [])

  useEffect(() => {
    if (source !== 'robot' || !cameraOn) {
      if (streamRetryTimer.current !== null) {
        window.clearTimeout(streamRetryTimer.current)
        streamRetryTimer.current = null
      }
      streamRetryDelay.current = 1000
    }
  }, [cameraOn, source])

  const handleRobotStreamLoad = useCallback(() => {
    streamRetryDelay.current = 1000
  }, [])

  const handleRobotStreamError = useCallback(() => {
    if (streamRetryTimer.current !== null) return
    const delay = streamRetryDelay.current
    streamRetryTimer.current = window.setTimeout(() => {
      streamRetryTimer.current = null
      setStreamVersion((version) => version + 1)
    }, delay)
    streamRetryDelay.current = Math.min(delay * 2, 5000)
  }, [])

  return (
    <>
      <div className="camera-stage">
        {source === 'webcam' && <video ref={videoRef} muted playsInline />}
        {source === 'robot' && cameraOn && (
          <img
            src={getRobotStreamUrl(streamVersion)}
            alt="Live stream from the Unitree R1 camera"
            onLoad={handleRobotStreamLoad}
            onError={handleRobotStreamError}
          />
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
            <span>
              {source === 'robot'
                ? 'Start the Unitree camera to begin'
                : 'Start the device camera to begin'}
            </span>
          </div>
        )}
      </div>

      {showRecognitionDetails && (
        <div className="camera-stage-details">
          <div className="panel metric-panel">
            <p className="eyebrow">CURRENT FRAME</p>
            <div className="metric-row">
              <div><strong>{detections.length}</strong><span>faces</span></div>
              <div><strong>{recognizedCount}</strong><span>recognized</span></div>
            </div>
            <div className="detection-list">
              {detections.length === 0 && (
                <p className="muted">No faces in the latest frame.</p>
              )}
              {detections.map((item, index) => (
                <div className="detection-item" key={`${item.name}-result-${index}`}>
                  <div className="avatar">
                    {item.name === 'unknown' ? '?' : item.name[0].toUpperCase()}
                  </div>
                  <div>
                    <strong>{item.name}</strong>
                    <span>Similarity {item.confidence.toFixed(3)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel control-panel">
            <div className="range-label">
              <span>Match threshold</span>
              <strong>{threshold.toFixed(2)}</strong>
            </div>
            <input
              type="range"
              min="0.3"
              max="0.7"
              step="0.01"
              value={threshold}
              onChange={(event) => onThresholdChange(Number(event.target.value))}
            />
            <p className="muted">Raise it to reduce false matches. Default: 0.45.</p>
            <div className="last-scan">
              Last response
              <strong>{lastScan ? lastScan.toLocaleTimeString() : '—'}</strong>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
