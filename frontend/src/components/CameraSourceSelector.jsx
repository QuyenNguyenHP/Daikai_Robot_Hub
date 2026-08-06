export function CameraSourceSelector({ value, onChange, disabled = false }) {
  return (
    <label className="source-picker">
      <span>Camera source</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
      >
        <option value="webcam">Device webcam</option>
        <option value="robot">Unitree R1 camera</option>
      </select>
    </label>
  )
}
