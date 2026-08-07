import { useEffect, useState } from 'react'
import { controlRobot, getRobotControlStatus, getRobotMode } from '../services/api'


const MOVEMENT_BUTTONS = [
  ['turn_left', '↶', 'Turn left'],
  ['forward', '↑', 'Forward'],
  ['turn_right', '↷', 'Turn right'],
  ['left', '←', 'Move left'],
  ['stop', '■', 'Stop'],
  ['right', '→', 'Move right'],
  [null, '', ''],
  ['backward', '↓', 'Backward'],
  [null, '', ''],
]


export function RobotControlPanel() {
  const [status, setStatus] = useState(null)
  const [mode, setMode] = useState(null)
  const [modeError, setModeError] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [message, setMessage] = useState(null)
  const [confirmEnable, setConfirmEnable] = useState(false)

  useEffect(() => {
    let active = true
    getRobotControlStatus()
      .then((result) => {
        if (active) setStatus(result)
      })
      .catch((error) => {
        if (active) setMessage({ type: 'error', text: error.message })
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const refreshMode = async () => {
      try {
        const result = await getRobotMode()
        if (!active) return
        setMode(result)
        setModeError('')
      } catch (error) {
        if (active) setModeError(error.message)
      }
    }
    refreshMode()
    const timer = window.setInterval(refreshMode, 2000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  const send = async (action) => {
    setBusyAction(action)
    setMessage(null)
    try {
      const result = await controlRobot(action)
      setStatus(result)
      try {
        setMode(await getRobotMode())
        setModeError('')
      } catch (error) {
        setModeError(error.message)
      }
      setMessage({
        type: 'success',
        text: `${action.replace('_', ' ')} command sent.`,
      })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
      try {
        setStatus(await getRobotControlStatus())
      } catch {
        // Keep the command error visible when status refresh also fails.
      }
    } finally {
      setBusyAction('')
    }
  }

  const configured = Boolean(status?.configured)
  const locomotionStarted = Boolean(status?.locomotion_started)
  const isStanceMode = mode?.fsm_id === 4
  const movementDisabled = !configured || !locomotionStarted || Boolean(busyAction)

  const confirmLocomotion = () => {
    setConfirmEnable(false)
    void send('enable')
  }

  return (
    <section className="panel robot-control-panel">
      <div className="control-title-row">
        <div>
          <p className="eyebrow">ROBOT CONTROL</p>
          <h2>Movement</h2>
        </div>
        <span className={`status-pill ${locomotionStarted ? 'live' : ''}`}>
          <i /> {locomotionStarted ? 'Enabled' : 'Locked'}
        </span>
      </div>

      <p className="control-safety">
        Use only in a clear, flat area. Each movement command lasts one second.
      </p>

      <div className="robot-mode">
        <span>FSM MODE</span>
        <strong>{mode?.display || (modeError ? 'Unavailable' : 'Checking…')}</strong>
      </div>

      <div className="control-mode-actions">
        <button
          type="button"
          className="button primary"
          disabled={
            !configured
            || Boolean(busyAction)
            || locomotionStarted
            || !isStanceMode
          }
          onClick={() => setConfirmEnable(true)}
        >
          {busyAction === 'enable' ? 'Enabling…' : 'Enable locomotion'}
        </button>
        <button
          type="button"
          className="button secondary"
          disabled={!configured || Boolean(busyAction) || !locomotionStarted}
          onClick={() => send('disable')}
        >
          {busyAction === 'disable' ? 'Disabling…' : 'Disable control'}
        </button>
      </div>

      <div className="movement-pad">
        {MOVEMENT_BUTTONS.map(([action, symbol, label], index) => (
          action ? (
            <button
              type="button"
              className={`movement-button ${action === 'stop' ? 'stop' : ''}`}
              key={action}
              disabled={action === 'stop'
                ? !configured || Boolean(busyAction)
                : movementDisabled}
              onClick={() => send(action)}
              title={label}
              aria-label={label}
            >
              <strong>{symbol}</strong>
              <span>{label}</span>
            </button>
          ) : <span key={`empty-${index}`} />
        ))}
      </div>

      {!configured && (
        <p className="battery-detail">Robot network is not configured.</p>
      )}
      {modeError && configured && (
        <p className="mode-detail">{modeError}</p>
      )}
      {message && (
        <p className={message.type === 'error' ? 'error-message' : 'success-message'}>
          {message.text}
        </p>
      )}

      {confirmEnable && (
        <div className="control-dialog-backdrop" role="presentation">
          <div
            className="control-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="control-warning-title"
          >
            <p className="eyebrow">SAFETY WARNING</p>
            <h3 id="control-warning-title">
              Please make sure the robot is standing on clear ground.
            </h3>
            <p>
              Enabling locomotion allows the robot to move immediately when a
              direction button is pressed.
            </p>
            <div className="control-dialog-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => setConfirmEnable(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button primary"
                onClick={confirmLocomotion}
              >
                Sure, let&apos;s start
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
