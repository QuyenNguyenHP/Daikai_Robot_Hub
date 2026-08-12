"""Persistent, feedback-seeded neck control for the Unitree R1."""

from __future__ import annotations

import math
import threading
import time


HEAD_PITCH = 29
HEAD_YAW = 30
CONTROL_PERIOD = 0.01
STATE_TIMEOUT = 1.0
RELEASE_DURATION = 1.0
STEP_RADIANS = math.radians(10.0)
PITCH_LIMIT = math.radians(30.0)
YAW_LIMIT = math.radians(60.0)
MAXIMUM_SPEED = math.radians(30.0)
MOVEMENT_TIMEOUT = 2.0
MOVEMENT_THRESHOLD = math.radians(0.5)
TARGET_TOLERANCE = math.radians(1.0)

ARM_SDK_JOINTS = (15, 16, 17, 18, 19, 22, 23, 24, 25, 26, 13, 29, 30)
ARM_SDK_KP = (
    50.0, 50.0, 40.0, 40.0, 30.0,
    50.0, 50.0, 40.0, 40.0, 30.0,
    50.0, 15.0, 15.0,
)
ARM_SDK_KD = (
    2.0, 2.0, 2.0, 2.0, 2.0,
    2.0, 2.0, 2.0, 2.0, 2.0,
    3.0, 1.0, 1.0,
)


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def move_toward(current: float, target: float, maximum_delta: float) -> float:
    return current + clamp(target - current, -maximum_delta, maximum_delta)


class RobotNeckController:
    """Publish smooth R1 neck targets while preserving all arm joint positions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state_ready = threading.Event()
        self._feedback_updated = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False
        self._last_state_time = 0.0
        self._target_pitch = 0.0
        self._target_yaw = 0.0
        self._command_pitch = 0.0
        self._command_yaw = 0.0
        self._measured_pitch = 0.0
        self._measured_yaw = 0.0
        self._publish_count = 0
        self._last_write_ok: bool | None = None
        self._fault: str | None = None

        self._crc = None
        self._cmd = None
        self._publisher = None
        self._subscriber = None

    @property
    def fault(self) -> str | None:
        with self._lock:
            return self._fault

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "active": self._active and not self._stop.is_set(),
                "fault": self._fault,
                "target_pitch_deg": round(math.degrees(self._target_pitch), 2),
                "target_yaw_deg": round(math.degrees(self._target_yaw), 2),
                "command_pitch_deg": round(math.degrees(self._command_pitch), 2),
                "command_yaw_deg": round(math.degrees(self._command_yaw), 2),
                "measured_pitch_deg": round(math.degrees(self._measured_pitch), 2),
                "measured_yaw_deg": round(math.degrees(self._measured_yaw), 2),
                "publish_count": self._publish_count,
                "last_write_ok": self._last_write_ok,
            }

    def initialize(self) -> None:
        from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber
        from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
        from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
        from unitree_sdk2py.utils.crc import CRC

        self._crc = CRC()
        self._cmd = unitree_hg_msg_dds__LowCmd_()
        self._publisher = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self._subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self._publisher.Init()
        self._subscriber.Init(self._handle_low_state, 10)

    def _handle_low_state(self, message) -> None:
        now = time.monotonic()
        pitch = float(message.motor_state[HEAD_PITCH].q)
        yaw = float(message.motor_state[HEAD_YAW].q)
        with self._lock:
            self._last_state_time = now
            self._measured_pitch = pitch
            self._measured_yaw = yaw
            if not self._state_ready.is_set():
                for joint, kp, kd in zip(ARM_SDK_JOINTS, ARM_SDK_KP, ARM_SDK_KD):
                    motor_cmd = self._cmd.motor_cmd[joint]
                    motor_cmd.tau = 0.0
                    motor_cmd.q = float(message.motor_state[joint].q)
                    motor_cmd.dq = 0.0
                    motor_cmd.kp = kp
                    motor_cmd.kd = kd
                self._target_pitch = pitch
                self._target_yaw = yaw
                self._command_pitch = pitch
                self._command_yaw = yaw
                self._state_ready.set()
        self._feedback_updated.set()

    def start(self, timeout: float = 5.0) -> bool:
        if not self._state_ready.wait(timeout):
            return False
        self._active = True
        self._thread = threading.Thread(
            target=self._control_loop,
            name="r1-neck-control",
            daemon=True,
        )
        self._thread.start()
        return True

    def apply(self, action: str) -> dict[str, object]:
        with self._lock:
            start_pitch = self._measured_pitch
            start_yaw = self._measured_yaw
            if action == "neck_up":
                self._target_pitch -= STEP_RADIANS
            elif action == "neck_down":
                self._target_pitch += STEP_RADIANS
            elif action == "neck_left":
                self._target_yaw += STEP_RADIANS
            elif action == "neck_right":
                self._target_yaw -= STEP_RADIANS
            elif action == "neck_center":
                self._target_pitch = 0.0
                self._target_yaw = 0.0
            else:
                raise ValueError(f"Unsupported neck action: {action}")

            self._target_pitch = clamp(
                self._target_pitch, -PITCH_LIMIT, PITCH_LIMIT
            )
            self._target_yaw = clamp(self._target_yaw, -YAW_LIMIT, YAW_LIMIT)
            target_pitch = self._target_pitch
            target_yaw = self._target_yaw

        self._feedback_updated.clear()
        deadline = time.monotonic() + MOVEMENT_TIMEOUT
        while time.monotonic() < deadline:
            self._feedback_updated.wait(0.1)
            self._feedback_updated.clear()
            with self._lock:
                if self._fault is not None:
                    raise RuntimeError(self._fault)
                measured_pitch = self._measured_pitch
                measured_yaw = self._measured_yaw

            if action in {"neck_up", "neck_down"}:
                moved = abs(measured_pitch - start_pitch) >= MOVEMENT_THRESHOLD
                reached = abs(measured_pitch - target_pitch) <= TARGET_TOLERANCE
            elif action in {"neck_left", "neck_right"}:
                moved = abs(measured_yaw - start_yaw) >= MOVEMENT_THRESHOLD
                reached = abs(measured_yaw - target_yaw) <= TARGET_TOLERANCE
            else:
                moved = (
                    abs(measured_pitch - start_pitch) >= MOVEMENT_THRESHOLD
                    or abs(measured_yaw - start_yaw) >= MOVEMENT_THRESHOLD
                )
                reached = (
                    abs(measured_pitch - target_pitch) <= TARGET_TOLERANCE
                    and abs(measured_yaw - target_yaw) <= TARGET_TOLERANCE
                )
            if moved or reached:
                return self.status()

        current = self.status()
        raise RuntimeError(
            "rt/arm_sdk published the neck target but rt/lowstate did not report "
            f"movement within {MOVEMENT_TIMEOUT:g}s; target="
            f"({current['target_pitch_deg']}, {current['target_yaw_deg']}) deg, "
            f"measured=({current['measured_pitch_deg']}, "
            f"{current['measured_yaw_deg']}) deg."
        )

    def _prepare_command(self, weight: float) -> None:
        pitch_cmd = self._cmd.motor_cmd[HEAD_PITCH]
        pitch_cmd.tau = 0.0
        pitch_cmd.q = self._command_pitch
        self._cmd.motor_cmd[HEAD_YAW].q = self._command_yaw
        self._cmd.mode_pr = round(clamp(weight, 0.0, 1.0) * 100.0)
        self._cmd.crc = self._crc.Crc(self._cmd)

    def _control_loop(self) -> None:
        next_tick = time.monotonic()
        maximum_delta = MAXIMUM_SPEED * CONTROL_PERIOD
        while not self._stop.is_set():
            now = time.monotonic()
            with self._lock:
                if now - self._last_state_time > STATE_TIMEOUT:
                    self._fault = "rt/lowstate timed out"
                    self._stop.set()
                    break
                self._command_pitch = move_toward(
                    self._command_pitch, self._target_pitch, maximum_delta
                )
                self._command_yaw = move_toward(
                    self._command_yaw, self._target_yaw, maximum_delta
                )
                self._prepare_command(1.0)
            write_ok = bool(self._publisher.Write(self._cmd))
            with self._lock:
                self._publish_count += 1
                self._last_write_ok = write_ok
                if not write_ok:
                    self._fault = "rt/arm_sdk publisher rejected the command"
                    self._stop.set()
            next_tick += CONTROL_PERIOD
            self._stop.wait(max(0.0, next_tick - time.monotonic()))

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._active and self._publisher is not None:
            steps = max(1, round(RELEASE_DURATION / CONTROL_PERIOD))
            for index in range(steps):
                with self._lock:
                    self._prepare_command(1.0 - (index + 1) / steps)
                self._publisher.Write(self._cmd)
                time.sleep(CONTROL_PERIOD)
            self._active = False
        if self._subscriber is not None:
            self._subscriber.Close()
        if self._publisher is not None:
            self._publisher.Close()
