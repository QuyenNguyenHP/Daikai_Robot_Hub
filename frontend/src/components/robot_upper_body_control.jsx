import { useEffect, useRef, useState } from 'react'
import {
  controlRobot,
  getRobotControlStatus,
  getRobotMode,
  setRobotUpperBodyJoint,
} from '../services/api'


const JOINTS = [
  { index: 15, name: 'L_SHOULDER_PITCH', min: -3.1416, max: 2.0944 },
  { index: 16, name: 'L_SHOULDER_ROLL', min: -0.2269, max: 2.4784 },
  { index: 17, name: 'L_SHOULDER_YAW', min: -1.9199, max: 1.9199 },
  { index: 18, name: 'L_ELBOW', min: -0.9757, max: 2.1850 },
  { index: 19, name: 'L_WRIST_ROLL', min: -1.9199, max: 1.9199 },
  { index: 22, name: 'R_SHOULDER_PITCH', min: -3.1416, max: 2.0944 },
  { index: 23, name: 'R_SHOULDER_ROLL', min: -2.4784, max: 0.2269 },
  { index: 24, name: 'R_SHOULDER_YAW', min: -1.9199, max: 1.9199 },
  { index: 25, name: 'R_ELBOW', min: -0.9757, max: 2.1850 },
  { index: 26, name: 'R_WRIST_ROLL', min: -1.9199, max: 1.9199 },
  { index: 29, name: 'HEAD_PITCH', min: -0.6283, max: 0.6283 },
  { index: 30, name: 'HEAD_YAW', min: -2.0071, max: 2.0071 },
  { index: 13, name: 'WAIST_YAW', min: -2.618, max: 2.618 },
]

const INITIAL_VALUES = Object.fromEntries(JOINTS.map(({ index }) => [index, 0]))


function toSliderPosition(value, joint) {
  return value >= 0
    ? (value / joint.max) * 100
    : (value / Math.abs(joint.min)) * 100
}


function toJointValue(sliderPosition, joint) {
  const value = sliderPosition >= 0
    ? (sliderPosition / 100) * joint.max
    : (sliderPosition / 100) * Math.abs(joint.min)
  return Number(value.toFixed(4))
}


function sliderFillStyle(sliderPosition) {
  const thumbPercent = (sliderPosition + 100) / 2
  return {
    '--fill-start': `${Math.min(50, thumbPercent)}%`,
    '--fill-end': `${Math.max(50, thumbPercent)}%`,
  }
}


export function RobotUpperBodyControl() {
  const [values, setValues] = useState(INITIAL_VALUES)
  const [status, setStatus] = useState(null)
  const [mode, setMode] = useState(null)
  const [toggleBusy, setToggleBusy] = useState(false)
  const [sendingTargets, setSendingTargets] = useState(false)
  const [message, setMessage] = useState('')
  const pendingTargets = useRef(new Map())
  const queueRunning = useRef(false)
  const debounceTimer = useRef(null)
  const previousMode = useRef(mode?.fsm_id)
  const configured = Boolean(status?.configured)
  const active = Boolean(status?.upper_body_control_active)
  const locomotionActive = [811, 816].includes(mode?.fsm_id)
  const controlsDisabled = !configured || !locomotionActive || !active || toggleBusy

  useEffect(() => () => {
    if (debounceTimer.current !== null) {
      window.clearTimeout(debounceTimer.current)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const refreshRobotState = async () => {
      const [statusResult, modeResult] = await Promise.allSettled([
        getRobotControlStatus(),
        getRobotMode(),
      ])
      if (!mounted) return
      if (statusResult.status === 'fulfilled') setStatus(statusResult.value)
      if (modeResult.status === 'fulfilled') setMode(modeResult.value)
    }
    void refreshRobotState()
    const timer = window.setInterval(refreshRobotState, 2000)
    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    const currentMode = mode?.fsm_id
    if (previousMode.current === 816 && currentMode !== 816) {
      setValues(INITIAL_VALUES)
      pendingTargets.current.clear()
      if (debounceTimer.current !== null) {
        window.clearTimeout(debounceTimer.current)
        debounceTimer.current = null
      }
      setMessage('')
    }
    previousMode.current = currentMode
  }, [mode?.fsm_id])

  const flushTargets = async () => {
    if (queueRunning.current) return
    queueRunning.current = true
    setSendingTargets(true)
    try {
      while (pendingTargets.current.size > 0) {
        const [jointIndex, position] = pendingTargets.current.entries().next().value
        pendingTargets.current.delete(jointIndex)
        try {
          const result = await setRobotUpperBodyJoint(jointIndex, position)
          setStatus(result)
          setMessage('')
        } catch (error) {
          setMessage(error.message)
        }
      }
    } finally {
      queueRunning.current = false
      setSendingTargets(false)
    }
  }

  const changeJoint = (jointIndex, position) => {
    setValues((current) => ({ ...current, [jointIndex]: position }))
    pendingTargets.current.set(jointIndex, position)
    if (debounceTimer.current !== null) {
      window.clearTimeout(debounceTimer.current)
    }
    debounceTimer.current = window.setTimeout(() => {
      debounceTimer.current = null
      void flushTargets()
    }, 100)
  }

  const toggleControl = async () => {
    if (toggleBusy) return
    if (active) {
      pendingTargets.current.clear()
      if (debounceTimer.current !== null) {
        window.clearTimeout(debounceTimer.current)
        debounceTimer.current = null
      }
    }
    setToggleBusy(true)
    setMessage('')
    try {
      const result = await controlRobot(
        active ? 'upper_body_disable' : 'upper_body_enable',
      )
      setStatus(result)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setToggleBusy(false)
    }
  }

  return (
    <div className="robot-control-group upper-body-control">
      <div className="upper-body-heading">
        <h3>Upper body <small>13 joints · radians</small></h3>
        <span>{sendingTargets ? 'Sending…' : active ? 'Active' : 'Released'}</span>
      </div>
      <button
        type="button"
        className={`button ${active ? 'secondary' : 'primary'}`}
        disabled={!configured || !locomotionActive || toggleBusy}
        onClick={toggleControl}
      >
        {toggleBusy
          ? active ? 'Releasing…' : 'Enabling…'
          : active ? 'Release upper-body control' : 'Enable upper-body control'}
      </button>
      <p className="mode-detail">
        Targets are limited by joint and sent to the robot in radians.
      </p>
      <div className="upper-body-sliders">
        {JOINTS.map((joint) => {
          const sliderPosition = toSliderPosition(values[joint.index], joint)
          return (
            <label
              className={`upper-body-slider ${
                joint.index === 13 ? 'waist-yaw-slider' : ''
              }`}
              key={joint.index}
            >
              <span className="upper-body-slider-label">
                <span><b>{joint.index}</b> {joint.name}</span>
                <output>{values[joint.index].toFixed(4)}</output>
              </span>
              <input
                type="range"
                min="-100"
                max="100"
                step="0.01"
                value={sliderPosition}
                style={sliderFillStyle(sliderPosition)}
                disabled={controlsDisabled}
                onChange={(event) => changeJoint(
                  joint.index,
                  toJointValue(Number(event.target.value), joint),
                )}
                aria-label={`${joint.name} position in radians`}
                aria-valuetext={`${values[joint.index].toFixed(4)} radians`}
              />
              <span className="upper-body-limits">
                <span>{joint.min.toFixed(4)}</span>
                <strong>0</strong>
                <span>{joint.max.toFixed(4)}</span>
              </span>
            </label>
          )
        })}
      </div>
      {message && <p className="error-message">{message}</p>}
    </div>
  )
}
