import { useCallback, useEffect, useRef, useState } from 'react'
import { getRobotServices, switchRobotService } from '../services/api'


export function RobotServicesPanel() {
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyService, setBusyService] = useState('')
  const [error, setError] = useState('')
  const mounted = useRef(true)
  const requestInFlight = useRef(false)

  const refresh = useCallback(async ({ quiet = false } = {}) => {
    if (requestInFlight.current) return
    requestInFlight.current = true
    if (!quiet) setLoading(true)
    try {
      const result = await getRobotServices()
      if (!mounted.current) return
      setServices(result.services || [])
      setError('')
    } catch (requestError) {
      if (mounted.current) setError(requestError.message)
    } finally {
      requestInFlight.current = false
      if (mounted.current && !quiet) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    const timer = window.setInterval(() => refresh({ quiet: true }), 5000)
    return () => {
      mounted.current = false
      window.clearInterval(timer)
    }
  }, [refresh])

  const toggle = async (service) => {
    if (requestInFlight.current || busyService || service.protected) return
    requestInFlight.current = true
    setBusyService(service.name)
    setError('')
    try {
      const result = await switchRobotService(service.name, !service.enabled)
      if (mounted.current) setServices(result.services || [])
    } catch (requestError) {
      if (mounted.current) setError(requestError.message)
    } finally {
      requestInFlight.current = false
      if (mounted.current) setBusyService('')
    }
  }

  const enabledCount = services.filter((service) => service.enabled).length

  return (
    <section className="panel services-panel">
      <div className="services-heading">
        <div>
          <p className="eyebrow">SYSTEM SERVICES</p>
          <h2>Robot services</h2>
        </div>
        <div className="services-summary">
          <span>{enabledCount} on</span>
          <span>{services.length - enabledCount} off</span>
          <button
            type="button"
            className="services-refresh"
            onClick={() => refresh()}
            disabled={loading || Boolean(busyService)}
            aria-label="Refresh robot services"
            title="Refresh robot services"
          >
            ↻
          </button>
        </div>
      </div>

      {loading && services.length === 0 ? (
        <p className="services-empty">Loading available services…</p>
      ) : services.length === 0 ? (
        <p className="services-empty">No services reported by the robot.</p>
      ) : (
        <div className="services-list">
          {services.map((service) => {
            const busy = busyService === service.name
            return (
              <div className="service-row" key={service.name}>
                <span className={`service-state ${service.enabled ? 'on' : ''}`}>
                  <i /> {service.enabled ? 'ON' : 'OFF'}
                </span>
                <div className="service-name">
                  <strong>{service.name}</strong>
                  {service.protected && <small>Protected by robot</small>}
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={service.enabled}
                  aria-label={`${service.enabled ? 'Turn off' : 'Turn on'} ${service.name}`}
                  className={`service-toggle ${service.enabled ? 'on' : ''}`}
                  disabled={service.protected || Boolean(busyService)}
                  onClick={() => toggle(service)}
                >
                  <span />
                  <b>{busy ? '…' : service.enabled ? 'On' : 'Off'}</b>
                </button>
              </div>
            )
          })}
        </div>
      )}

      {error && <p className="error-message services-error">{error}</p>}
    </section>
  )
}
