export function ThresholdControl({ threshold, lastScan, onChange }) {
  return (
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
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <p className="muted">Raise it to reduce false matches. Default: 0.45.</p>
      <div className="last-scan">
        Last response
        <strong>{lastScan ? lastScan.toLocaleTimeString() : '—'}</strong>
      </div>
    </div>
  )
}
