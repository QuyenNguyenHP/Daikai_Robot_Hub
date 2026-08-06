import { getRobotStreamUrl } from '../services/api'


export function CameraStage({
  videoRef,
  detections = [],
  cameraOn = false,
  source = 'webcam',
}) {
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
