"""Persistent, feedback-seeded upper-body control for the Unitree R1."""

from __future__ import annotations

import math
import threading
import time


CONTROL_PERIOD = 0.01
STATE_TIMEOUT = 1.0
RELEASE_DURATION = 1.0
STEP_RADIANS = math.radians(10.0)
MAXIMUM_SPEED = math.radians(30.0)

# LowCmd motor index: (name, minimum radians, maximum radians, kp, kd)
UPPER_BODY_JOINTS = {
    13: ("WAIST_YAW", -2.618, 2.618, 50.0, 3.0),
    15: ("L_SHOULDER_PITCH", -3.1416, 2.0944, 50.0, 2.0),
    16: ("L_SHOULDER_ROLL", -0.2269, 2.4784, 50.0, 2.0),
    17: ("L_SHOULDER_YAW", -1.9199, 1.9199, 40.0, 2.0),
    18: ("L_ELBOW", -0.9757, 2.1850, 40.0, 2.0),
    19: ("L_WRIST_ROLL", -1.9199, 1.9199, 30.0, 2.0),
    22: ("R_SHOULDER_PITCH", -3.1416, 2.0944, 50.0, 2.0),
    23: ("R_SHOULDER_ROLL", -2.4784, 0.2269, 50.0, 2.0),
    24: ("R_SHOULDER_YAW", -1.9199, 1.9199, 40.0, 2.0),
    25: ("R_ELBOW", -0.9757, 2.1850, 40.0, 2.0),
    26: ("R_WRIST_ROLL", -1.9199, 1.9199, 30.0, 2.0),
    29: ("HEAD_PITCH", -0.6283, 0.6283, 15.0, 1.0),
    30: ("HEAD_YAW", -2.0071, 2.0071, 15.0, 1.0),
}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def move_toward(current: float, target: float, maximum_delta: float) -> float:
    return current + clamp(target - current, -maximum_delta, maximum_delta)


class RobotUpperBodyController:
    """Publish smooth R1 upper-body targets while retaining unmodified joints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state_ready = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False
        self._last_state_time = 0.0
        self._targets = {index: 0.0 for index in UPPER_BODY_JOINTS}
        self._commands = {index: 0.0 for index in UPPER_BODY_JOINTS}
        self._measured = {index: 0.0 for index in UPPER_BODY_JOINTS}
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
            joints = {
                str(index): {
                    "name": spec[0],
                    "target": round(self._targets[index], 4),
                    "command": round(self._commands[index], 4),
                    "measured": round(self._measured[index], 4),
                }
                for index, spec in UPPER_BODY_JOINTS.items()
            }
            return {
                "active": self._active and not self._stop.is_set(),
                "fault": self._fault,
                "joints": joints,
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
        with self._lock:
            self._last_state_time = now
            for index in UPPER_BODY_JOINTS:
                self._measured[index] = float(message.motor_state[index].q)

            if not self._state_ready.is_set():
                for index, (_, _, _, kp, kd) in UPPER_BODY_JOINTS.items():
                    position = self._measured[index]
                    motor_cmd = self._cmd.motor_cmd[index]
                    motor_cmd.tau = 0.0
                    motor_cmd.q = position
                    motor_cmd.dq = 0.0
                    motor_cmd.kp = kp
                    motor_cmd.kd = kd
                    self._targets[index] = position
                    self._commands[index] = position
                self._state_ready.set()

    def start(self, timeout: float = 5.0) -> bool:
        if not self._state_ready.wait(timeout):
            return False
        self._active = True
        self._thread = threading.Thread(
            target=self._control_loop,
            name="r1-upper-body-control",
            daemon=True,
        )
        self._thread.start()
        return True

    def set_joint_target(self, joint_index: int, position: float) -> dict[str, object]:
        if joint_index not in UPPER_BODY_JOINTS:
            raise ValueError(f"Motor index {joint_index} is not an upper-body joint.")
        if not math.isfinite(position):
            raise ValueError("Joint position must be a finite number.")

        name, lower, upper, _, _ = UPPER_BODY_JOINTS[joint_index]
        if not lower <= position <= upper:
            raise ValueError(
                f"{name} position must be between {lower} and {upper} radians."
            )
        with self._lock:
            self._targets[joint_index] = position
        return self.status()

    def apply_neck_action(self, action: str) -> dict[str, object]:
        with self._lock:
            pitch = self._targets[29]
            yaw = self._targets[30]
            if action == "neck_up":
                pitch -= STEP_RADIANS
            elif action == "neck_down":
                pitch += STEP_RADIANS
            elif action == "neck_left":
                yaw += STEP_RADIANS
            elif action == "neck_right":
                yaw -= STEP_RADIANS
            elif action == "neck_center":
                pitch = 0.0
                yaw = 0.0
            else:
                raise ValueError(f"Unsupported neck action: {action}")

            self._targets[29] = clamp(
                pitch,
                UPPER_BODY_JOINTS[29][1],
                UPPER_BODY_JOINTS[29][2],
            )
            self._targets[30] = clamp(
                yaw,
                UPPER_BODY_JOINTS[30][1],
                UPPER_BODY_JOINTS[30][2],
            )
        return self.status()

    def _prepare_command(self, weight: float) -> None:
        for index in UPPER_BODY_JOINTS:
            self._cmd.motor_cmd[index].q = self._commands[index]
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
                for index in UPPER_BODY_JOINTS:
                    self._commands[index] = move_toward(
                        self._commands[index], self._targets[index], maximum_delta
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
