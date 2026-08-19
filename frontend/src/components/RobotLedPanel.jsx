import { useState } from 'react'
import { setRobotLed } from '../services/api'


const PRESETS = [
  ['White', '#ffffff'],
  ['Red', '#ff0000'],
  ['Green', '#00ff00'],
  ['Blue', '#0000ff'],
  ['Yellow', '#ffff00'],
  ['Cyan', '#00ffff'],
  ['Magenta', '#ff00ff'],
  ['Orange', '#ff8000'],
]


function hexToRgb(hex) {
  return {
    red: Number.parseInt(hex.slice(1, 3), 16),
    green: Number.parseInt(hex.slice(3, 5), 16),
    blue: Number.parseInt(hex.slice(5, 7), 16),
  }
}


export function RobotLedPanel() {
  const [color, setColor] = useState('#ffffff')
  const [appliedColor, setAppliedColor] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const [keepColor, setKeepColor] = useState(false)
  const rgb = hexToRgb(color)

  const apply = async (nextColor = color, keepOn = keepColor) => {
    if (busy) return
    const channels = hexToRgb(nextColor)
    setColor(nextColor)
    setBusy(true)
    setMessage(null)
    try {
      await setRobotLed(channels.red, channels.green, channels.blue, keepOn)
      setAppliedColor(nextColor)
      setMessage({ type: 'success', text: nextColor === '#000000' ? 'LED turned off.' : 'LED color updated.' })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel led-panel">
      <div className="panel-heading led-heading">
        <div>
          <p className="eyebrow">ROBOT LIGHT</p>
          <h2>LED color</h2>
        </div>
        <div className="led-current-indicator">
          <span
            className="led-current-swatch"
            style={{ background: appliedColor || '#172536' }}
            title={appliedColor ? `Applied color ${appliedColor}` : 'No color applied yet'}
          />
        </div>
      </div>

      <div className="led-presets">
        {PRESETS.map(([name, hex]) => (
          <button
            type="button"
            className={`led-preset ${color === hex ? 'selected' : ''}`}
            key={name}
            disabled={busy}
            onClick={() => apply(hex)}
            title={`Set LED to ${name}`}
          >
            <span style={{ background: hex }} />
            {name}
          </button>
        ))}
      </div>

      <div className="led-custom-control">
        <label>
          <span>Custom color</span>
          <input
            type="color"
            value={color}
            disabled={busy}
            onChange={(event) => setColor(event.target.value)}
          />
        </label>
        <output>R {rgb.red} · G {rgb.green} · B {rgb.blue}</output>
        <button
          type="button"
          className="button primary"
          disabled={busy}
          onClick={() => apply()}
        >
          {busy ? 'Sending…' : 'Apply color'}
        </button>
        <button
          type="button"
          className="button secondary led-off-button"
          disabled={busy}
          onClick={() => {
            setKeepColor(false)
            void apply('#000000', false)
          }}
        >
          Turn off
        </button>
      </div>

      <label className="led-keep-toggle">
        <input
          type="checkbox"
          checked={keepColor}
          disabled={busy}
          onChange={(event) => {
            const enabled = event.target.checked
            setKeepColor(enabled)
            if (appliedColor) void apply(appliedColor, enabled)
          }}
        />
        <span>
          <strong>Keep color always on</strong>
          Reapply the selected color every 0.5 seconds.
        </span>
      </label>

      {message && (
        <p className={message.type === 'error' ? 'error-message' : 'success-message'}>
          {message.text}
        </p>
      )}
    </section>
  )
}
