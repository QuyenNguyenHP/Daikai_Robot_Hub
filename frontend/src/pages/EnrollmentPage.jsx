import { useEffect, useRef, useState } from 'react'
import { CameraStage } from '../components/CameraStage'
import { useCameraSource } from '../hooks/useCameraSource'
import { enrollPerson, getRobotSnapshot } from '../services/api'


export function EnrollmentPage({ onEnrolled }) {
  const videoRef = useRef(null)
  const filesRef = useRef([])
  const camera = useCameraSource(videoRef, 'robot')
  const [name, setName] = useState('')
  const [files, setFiles] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [captureError, setCaptureError] = useState('')
  const [message, setMessage] = useState(null)

  useEffect(() => {
    filesRef.current = files
  }, [files])

  useEffect(() => () => {
    filesRef.current.forEach(({ preview }) => URL.revokeObjectURL(preview))
  }, [])

  const addFiles = (newFiles) => {
    setFiles((current) => {
      const available = Math.max(30 - current.length, 0)
      const additions = Array.from(newFiles).slice(0, available).map((file) => ({
        file,
        preview: URL.createObjectURL(file),
      }))
      return [...current, ...additions]
    })
  }

  const takePhoto = async () => {
    try {
      const blob = await getRobotSnapshot()
      if (!blob || files.length >= 30) return
      addFiles([
        new File([blob], `robot-${Date.now()}.jpg`, { type: 'image/jpeg' }),
      ])
      setCaptureError('')
    } catch (error) {
      setCaptureError(error.message)
    }
  }

  const toggleCamera = async () => {
    setCaptureError('')
    if (camera.cameraOn) camera.stopCamera()
    else await camera.startCamera()
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
      const result = await enrollPerson(name, files.map(({ file }) => file))
      setMessage({
        type: 'success',
        text: `Saved ${result.accepted} valid samples for ${result.name}. ${result.rejected.length} rejected.`,
      })
      files.forEach(({ preview }) => URL.revokeObjectURL(preview))
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
        <input
          id="person-name"
          className="text-input"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Mit"
          maxLength="80"
        />

        <div className="upload-zone">
          <input
            id="photo-upload"
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => addFiles(event.target.files)}
          />
          <label htmlFor="photo-upload">
            <strong>Choose photos</strong>
            <span>JPG, PNG or WebP · up to 30 files · 10 MB each</span>
          </label>
        </div>

        <div className="thumb-grid">
          {files.map((item, index) => (
            <button
              type="button"
              className="thumb"
              key={item.preview}
              onClick={() => removePhoto(index)}
              title="Remove photo"
            >
              <img src={item.preview} alt={`Sample ${index + 1}`} /><span>×</span>
            </button>
          ))}
        </div>
        {message && (
          <p className={message.type === 'error' ? 'error-message' : 'success-message'}>
            {message.text}
          </p>
        )}
        <button
          className="button primary full"
          disabled={submitting || !name.trim() || files.length === 0}
        >
          {submitting ? 'Processing faces…' : 'Create face profile'}
        </button>
      </form>

      <div className="panel capture-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">CAMERA SAMPLES</p><h2>Capture photos</h2></div>
        </div>
        <CameraStage
          videoRef={videoRef}
          cameraOn={camera.cameraOn}
          source="robot"
        />
        <div className="camera-actions">
          <button
            className="button secondary"
            type="button"
            disabled={camera.starting}
            onClick={toggleCamera}
          >
            {camera.starting ? 'Connecting…' : camera.cameraOn ? 'Stop camera' : 'Start camera'}
          </button>
          <button
            className="button primary"
            type="button"
            disabled={!camera.cameraOn || files.length >= 30}
            onClick={takePhoto}
          >
            Capture sample
          </button>
        </div>
        {(captureError || camera.error) && (
          <p className="error-message">{captureError || camera.error}</p>
        )}
        <div className="tips">
          <strong>For better recognition</strong>
          <span>Use 10–20 clear photos with small changes in angle, distance and expression. Keep one face per photo.</span>
        </div>
      </div>
    </section>
  )
}
