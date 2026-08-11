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

const VISION_BUTTONS = [
  [null, '', ''],
  ['neck_up', '↑', 'Look up'],
  [null, '', ''],
  ['neck_left', '←', 'Look left'],
  ['neck_center', '●', 'Center'],
  ['neck_right', '→', 'Look right'],
  [null, '', ''],
  ['neck_down', '↓', 'Look down'],
  [null, '', ''],
]

const ACTION_BUTTONS = [
  ['arm_blow_kiss_both', '💋', 'Both-hand kiss', 11],
  ['arm_blow_kiss_left', '💋', 'Left-hand kiss', 12],
  ['arm_blow_kiss_right', '💋', 'Right-hand kiss', 13],
  ['arm_both_hands_up', '🙌', 'Both hands up', 15],
  ['arm_clap', '👏', 'Clap', 17],
  ['arm_high_five', '✋', 'High five', 18],
  ['arm_hug', '🫶', 'Hug', 19],
  ['arm_refuse', '🙅', 'Refuse', 22],
  ['arm_right_hand_up', '🙋', 'Right hand up', 23],
  ['arm_ultraman_ray', '✨', 'Ultraman ray', 24],
  ['arm_wave_under_head', '👋', 'Wave below head', 25],
  ['arm_wave', '👋', 'Wave above head', 26],
  ['arm_handshake', '🤝', 'Handshake', 27],
  ['arm_box_left_win', '✊', 'Left-hand win', 28],
  ['arm_box_right_win', '✊', 'Right-hand win', 29],
  ['arm_box_both_win', '🤜', 'Both-hands win', 30],
  ['arm_extend_right_arm', '👉', 'Extend right arm', 31],
  ['arm_right_hand_heart', '❤', 'Hand on heart', 33],
  ['arm_hands_up_right', '🙌', 'Hands up right', 34],
  ['arm_emphasize', '☝', 'Emphasize', 35],
  ['arm_forward_push', '🤲', 'Forward push', 36],
  ['arm_release', '↩', 'Release arms', 99],
]


export function RobotControlPanel() {
  const [status, setStatus] = useState(null)
  const [mode, setMode] = useState(null)
  const [modeError, setModeError] = useState('')
  const [busyAction, setBusyAction] = useState('')
  const [message, setMessage] = useState(null)
  const [confirmEnable, setConfirmEnable] = useState(false)
  const [controlLocked, setControlLocked] = useState(false)

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
      if (action === 'enable') setControlLocked(false)
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
  const isZeroTorqueMode = mode?.fsm_id === 0
  const isStanceMode = mode?.fsm_id === 4
  const isLocomotionMode = mode?.fsm_id === 811
  const locomotionActive = isLocomotionMode && !controlLocked
  const canToggleStanceMode = isZeroTorqueMode || isStanceMode || isLocomotionMode
  const stanceModeAction = isStanceMode ? 'zero_torque' : 'stance'
  const commandDisabled = !configured || !locomotionActive || Boolean(busyAction)

  const confirmLocomotion = () => {
    setConfirmEnable(false)
    void send('enable')
  }

  const sendModeAction = (action) => {
    void send(action)
  }

  const toggleStanceMode = () => {
    if (isLocomotionMode) {
      setControlLocked(true)
      setStatus((current) => ({
        ...current,
        locomotion_started: false,
      }))
      setMode({
        configured,
        fsm_id: 4,
        fsm_name: 'STANCE',
        display: 'STANCE (ID 4)',
      })
      setModeError('')
    }
    sendModeAction(stanceModeAction)
  }

  return (
    <section className="panel robot-control-panel">
      <div className="control-title-row">
        <div>
          <p className="eyebrow">ROBOT CONTROL</p>
          <h2>Robot controls</h2>
        </div>
        <span className={`status-pill ${locomotionActive ? 'live' : ''}`}>
          <i /> {locomotionActive ? 'Enabled' : 'Locked'}
        </span>
      </div>

      {message && (
        <p className={message.type === 'error' ? 'error-message' : 'success-message'}>
          {message.text}
        </p>
      )}

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
          className="button secondary"
          disabled={!configured || Boolean(busyAction) || !canToggleStanceMode}
          onClick={toggleStanceMode}
        >
          {busyAction === 'stance'
            ? 'Entering stance…'
            : busyAction === 'zero_torque'
              ? 'Entering zero torque…'
              : isStanceMode
                ? 'Enter zero torque mode'
                : 'Enter stance mode'}
        </button>
        <button
          type="button"
          className="button primary"
          disabled={
            !configured
            || Boolean(busyAction)
            || locomotionActive
            || !isStanceMode
          }
          onClick={() => setConfirmEnable(true)}
        >
          {busyAction === 'enable' ? 'Enabling…' : 'Enable locomotion'}
        </button>
      </div>

      <div className="robot-control-group">
        <h3>Moving</h3>
        <div className="movement-pad">
          {MOVEMENT_BUTTONS.map(([action, symbol, label], index) => (
            action ? (
              <button
                type="button"
                className={`movement-button ${action === 'stop' ? 'stop' : ''}`}
                key={action}
                disabled={commandDisabled}
                onClick={() => send(action)}
                title={label}
                aria-label={label}
              >
                <strong>{symbol}</strong>
                <span>{label}</span>
              </button>
            ) : <span key={`moving-empty-${index}`} />
          ))}
        </div>
      </div>

      <div className="robot-control-group">
        <h3>Vision <small>Neck movement</small></h3>
        <div className="movement-pad vision-pad">
          {VISION_BUTTONS.map(([action, symbol, label], index) => (
            action ? (
              <button
                type="button"
                className="movement-button"
                key={action}
                disabled={commandDisabled}
                onClick={() => send(action)}
                title={label}
                aria-label={label}
              >
                <strong>{symbol}</strong>
                <span>{label}</span>
              </button>
            ) : <span key={`vision-empty-${index}`} />
          ))}
        </div>
      </div>

      <div className="robot-control-group">
        <h3>Action</h3>
        <div className="action-pad">
          {ACTION_BUTTONS.map(([action, symbol, label, actionId]) => (
            <button
              type="button"
              className="movement-button action-button"
              key={action}
              disabled={commandDisabled}
              onClick={() => send(action)}
            >
              <strong>{symbol}</strong>
              <span>{label}</span>
              <small>ID {actionId}</small>
            </button>
          ))}
        </div>
      </div>

      {!configured && (
        <p className="battery-detail">Robot network is not configured.</p>
      )}
      {modeError && configured && (
        <p className="mode-detail">{modeError}</p>
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
