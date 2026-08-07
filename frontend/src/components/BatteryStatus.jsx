import { useEffect, useState } from 'react'
import { getRobotBattery } from '../services/api'


function BatteryIcon({ percent = 0, connected }) {
  const fill = connected ? Math.max(0, Math.min(100, percent)) : 0
  return (
    <span className="battery-icon" aria-hidden="true">
      <span className="battery-icon-fill" style={{ width: `${fill}%` }} />
    </span>
  )
}

function value(input, suffix = '') {
  return input === null || input === undefined ? '—' : `${input}${suffix}`
}

export function BatteryStatus() {
  const [status, setStatus] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const refresh = async () => {
      try {
        const result = await getRobotBattery()
        if (!active) return
        setStatus(result)
        setError('')
      } catch (requestError) {
        if (active) setError(requestError.message)
      }
    }
    refresh()
    const timer = window.setInterval(refresh, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  const battery = status?.battery
  const connected = Boolean(status?.connected && battery)
  const detail = error
    ? 'Battery API unavailable'
    : status?.error || (!status?.configured
      ? 'Robot network is not configured'
      : !battery
        ? 'Waiting for battery telemetry'
        : status?.state === 'stale' ? 'Battery telemetry is stale' : '')

  return (
    <section className={`panel battery-panel ${connected ? 'connected' : ''}`}>
      <div className="battery-title-row">
        <div className="battery-charge">
          <BatteryIcon percent={battery?.charge_percent} connected={connected} />
          <div><span>BATTERY</span><strong>{value(battery?.charge_percent, '%')}</strong></div>
        </div>
        <span className={`battery-health ${battery?.health === 'HEALTHY' ? 'good' : ''}`}>
          {battery?.health || 'OFFLINE'}
        </span>
      </div>
      <dl className="battery-metrics">
        <div><dt>VOLTAGE</dt><dd>{value(battery?.voltage_v, ' V')}</dd></div>
        <div><dt>CURRENT</dt><dd>{value(battery?.current_a, ' A')}</dd></div>
        <div className="wide"><dt>STATE</dt><dd>{battery?.charge_state || '—'}</dd></div>
        <div className="wide"><dt>TEMP</dt><dd>{value(battery?.max_temperature_c, ' °C')} <small>MAX</small></dd></div>
        <div><dt>CELLS</dt><dd>{battery?.cells || '—'}</dd></div>
        <div><dt>IMBALANCE</dt><dd>{value(battery?.balance_mv, ' mV')} <small>{battery?.balance ? `· ${battery.balance}` : ''}</small></dd></div>
      </dl>
      {detail && <p className="battery-detail">{detail}</p>}
    </section>
  )
}
