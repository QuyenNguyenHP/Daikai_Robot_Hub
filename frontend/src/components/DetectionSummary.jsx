export function DetectionSummary({ detections }) {
  const recognizedCount = detections.filter(({ name }) => name !== 'unknown').length

  return (
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
  )
}
