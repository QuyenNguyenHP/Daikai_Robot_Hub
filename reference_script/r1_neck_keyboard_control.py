#!/usr/bin/env python3
"""Control the Unitree R1 neck with arrow keys through ``rt/arm_sdk``."""

import argparse
import json
import math
import os
import select
import signal
import sys
import termios
import threading
import time
import tty
from typing import Optional, Tuple

from unitree_sdk2py.core.channel import (
    ChannelFactoryInitialize,
    ChannelPublisher,
    ChannelSubscriber,
)
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.r1.loco.r1_loco_api import ROBOT_API_ID_LOCO_GET_FSM_ID
from unitree_sdk2py.r1.loco.r1_loco_client import LocoClient
from unitree_sdk2py.utils.crc import CRC


# R1 logical head joints 24 and 25 map to these LowCmd/LowState IDL slots.
HEAD_PITCH = 29
HEAD_YAW = 30
LOCOMOTION_FSM_ID = 811

CONTROL_PERIOD = 0.01  # 100 Hz, matching Unitree's R1 rt/arm_sdk example.
STATE_TIMEOUT = 1.0
RELEASE_DURATION = 1.0

# R1's arm_sdk weight applies to all of these joints, not only the neck. Seed
# every command from feedback before raising the weight to prevent a posture
# jump. Ordering and gains follow Unitree's R1 ArmSdk wrapper/example.
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Control the R1 neck on rt/arm_sdk while locomotion mode remains active."
        )
    )
    parser.add_argument(
        "network_interface",
        help="Network interface connected to the robot, for example enp2s0",
    )
    parser.add_argument(
        "--step-deg",
        type=float,
        default=5.0,
        help="Target change for each arrow-key press (default: 5 degrees)",
    )
    parser.add_argument(
        "--pitch-limit-deg",
        type=float,
        default=30.0,
        help="Symmetric pitch target limit (default: 30 degrees)",
    )
    parser.add_argument(
        "--yaw-limit-deg",
        type=float,
        default=60.0,
        help="Symmetric yaw target limit (default: 60 degrees)",
    )
    parser.add_argument(
        "--max-speed-deg-s",
        type=float,
        default=45.0,
        help="Maximum neck target slew rate (default: 45 degrees/second)",
    )
    args = parser.parse_args()

    if args.step_deg <= 0.0:
        parser.error("--step-deg must be greater than zero")
    if args.pitch_limit_deg <= 0.0 or args.yaw_limit_deg <= 0.0:
        parser.error("joint limits must be greater than zero")
    if args.max_speed_deg_s <= 0.0:
        parser.error("--max-speed-deg-s must be greater than zero")
    if not sys.stdin.isatty():
        parser.error("keyboard control requires an interactive terminal")
    return args


def get_fsm_id(client: LocoClient) -> Tuple[int, Optional[int]]:
    """Query API 7001, registered by R1's LocoClient but not publicly wrapped."""
    code, data = client._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
    if code != 0:
        return code, None
    try:
        return code, int(json.loads(data)["data"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return code, None


class NeckController:
    def __init__(
        self,
        pitch_limit: float,
        yaw_limit: float,
        maximum_speed: float,
    ) -> None:
        self.pitch_limit = pitch_limit
        self.yaw_limit = yaw_limit
        self.maximum_speed = maximum_speed

        self._lock = threading.Lock()
        self._state_ready = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._last_state_time = 0.0
        self._target_pitch = 0.0
        self._target_yaw = 0.0
        self._command_pitch = 0.0
        self._command_yaw = 0.0
        self._measured_pitch = 0.0
        self._measured_yaw = 0.0
        self._fault: Optional[str] = None

        self._crc = CRC()
        self._cmd = unitree_hg_msg_dds__LowCmd_()
        self._publisher = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self._subscriber = ChannelSubscriber("rt/lowstate", LowState_)

    @property
    def fault(self) -> Optional[str]:
        with self._lock:
            return self._fault

    def initialize(self) -> None:
        self._publisher.Init()
        self._subscriber.Init(self._handle_low_state, 10)

    def _handle_low_state(self, msg: LowState_) -> None:
        now = time.monotonic()
        pitch = float(msg.motor_state[HEAD_PITCH].q)
        yaw = float(msg.motor_state[HEAD_YAW].q)
        with self._lock:
            self._last_state_time = now
            self._measured_pitch = pitch
            self._measured_yaw = yaw
            if not self._state_ready.is_set():
                # R1's mode_pr weight claims all arm_sdk joints. Initialize
                # each one from feedback so startup causes no posture step.
                for joint, kp, kd in zip(ARM_SDK_JOINTS, ARM_SDK_KP, ARM_SDK_KD):
                    motor_cmd = self._cmd.motor_cmd[joint]
                    motor_cmd.tau = 0.0
                    motor_cmd.q = float(msg.motor_state[joint].q)
                    motor_cmd.dq = 0.0
                    motor_cmd.kp = kp
                    motor_cmd.kd = kd
                self._target_pitch = pitch
                self._target_yaw = yaw
                self._command_pitch = pitch
                self._command_yaw = yaw
                self._state_ready.set()

    def start(self, timeout: float = 5.0) -> bool:
        if not self._state_ready.wait(timeout):
            return False
        self._thread = threading.Thread(
            target=self._control_loop, name="r1-neck-control", daemon=True
        )
        self._active = True
        self._thread.start()
        return True

    def adjust_target(self, pitch_delta: float, yaw_delta: float) -> Tuple[float, float]:
        with self._lock:
            self._target_pitch = clamp(
                self._target_pitch + pitch_delta,
                -self.pitch_limit,
                self.pitch_limit,
            )
            self._target_yaw = clamp(
                self._target_yaw + yaw_delta,
                -self.yaw_limit,
                self.yaw_limit,
            )
            return self._target_pitch, self._target_yaw

    def center_target(self) -> Tuple[float, float]:
        with self._lock:
            self._target_pitch = 0.0
            self._target_yaw = 0.0
            return self._target_pitch, self._target_yaw

    def status(self) -> Tuple[float, float, float, float]:
        with self._lock:
            return (
                self._target_pitch,
                self._target_yaw,
                self._measured_pitch,
                self._measured_yaw,
            )

    def _prepare_command(self, weight: float) -> None:
        pitch_cmd = self._cmd.motor_cmd[HEAD_PITCH]
        pitch_cmd.tau = 0.0
        pitch_cmd.q = self._command_pitch

        yaw_cmd = self._cmd.motor_cmd[HEAD_YAW]
        yaw_cmd.q = self._command_yaw

        # R1 differs from G1/H2: the R1 ArmSdk wrapper stores its 0..1 blend
        # weight as an integer percentage in LowCmd.mode_pr.
        self._cmd.mode_pr = round(clamp(weight, 0.0, 1.0) * 100.0)
        self._cmd.crc = self._crc.Crc(self._cmd)

    def _control_loop(self) -> None:
        next_tick = time.monotonic()
        maximum_delta = self.maximum_speed * CONTROL_PERIOD

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
            self._publisher.Write(self._cmd)

            next_tick += CONTROL_PERIOD
            self._stop.wait(max(0.0, next_tick - time.monotonic()))

    def release_and_close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

        if self._active:
            # Hold the last command while smoothly returning ownership to the
            # locomotion controller. If control never started, do not publish.
            steps = max(1, round(RELEASE_DURATION / CONTROL_PERIOD))
            for index in range(steps):
                weight = 1.0 - (index + 1) / steps
                with self._lock:
                    self._prepare_command(weight)
                self._publisher.Write(self._cmd)
                time.sleep(CONTROL_PERIOD)
            self._active = False

        self._subscriber.Close()
        self._publisher.Close()


def read_key(fd: int) -> str:
    """Read one key, combining the three-byte ANSI arrow-key sequences."""
    first = os.read(fd, 1)
    if first != b"\x1b":
        return first.decode(errors="ignore").lower()

    readable, _, _ = select.select([fd], [], [], 0.04)
    if not readable:
        return "escape"
    second = os.read(fd, 1)
    if second != b"[":
        return "escape"

    readable, _, _ = select.select([fd], [], [], 0.04)
    if not readable:
        return "escape"
    return {b"A": "up", b"B": "down", b"C": "right", b"D": "left"}.get(
        os.read(fd, 1), "unknown"
    )


def print_status(
    pitch: float, yaw: float, measured_pitch: float, measured_yaw: float
) -> None:
    print(
        f"\rTarget: pitch={math.degrees(pitch):+6.1f} deg, "
        f"yaw={math.degrees(yaw):+6.1f} deg | "
        f"Measured: pitch={math.degrees(measured_pitch):+6.1f} deg, "
        f"yaw={math.degrees(measured_yaw):+6.1f} deg       ",
        end="",
        flush=True,
    )


def main() -> int:
    args = parse_args()
    step = math.radians(args.step_deg)

    print("WARNING: This program takes control of the R1 neck through rt/arm_sdk.")
    print("Keep the robot in a clear area and keep an emergency stop available.")
    confirmation = input("Type NECK to continue: ").strip()
    if confirmation != "NECK":
        print("Cancelled; no neck command was sent.")
        return 1

    ChannelFactoryInitialize(0, args.network_interface)

    loco_client = LocoClient()
    loco_client.SetTimeout(3.0)
    loco_client.Init()
    code, fsm_id = get_fsm_id(loco_client)
    if code != 0:
        print(f"Cannot verify locomotion mode: FSM query failed with code {code}.")
        return 2
    if fsm_id != LOCOMOTION_FSM_ID:
        mode = "unknown" if fsm_id is None else str(fsm_id)
        print(f"Robot FSM is {mode}, not locomotion ({LOCOMOTION_FSM_ID}).")
        print("Enter locomotion mode first, then run this script again.")
        return 2

    controller = NeckController(
        pitch_limit=math.radians(args.pitch_limit_deg),
        yaw_limit=math.radians(args.yaw_limit_deg),
        maximum_speed=math.radians(args.max_speed_deg_s),
    )
    controller.initialize()
    if not controller.start():
        controller.release_and_close()
        print("Timed out waiting for rt/lowstate; no neck control started.")
        return 3

    should_stop = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    print("\nControls:")
    print("  Up/Down     pitch up/down")
    print("  Left/Right  yaw left/right")
    print("  C or 0      center both targets")
    print("  Q or ESC    release neck control and quit")
    print_status(*controller.status())

    fd = sys.stdin.fileno()
    old_terminal_settings = termios.tcgetattr(fd)
    exit_code = 0
    next_status_time = time.monotonic()
    try:
        tty.setcbreak(fd)
        while not should_stop:
            if controller.fault is not None:
                print(f"\nSafety stop: {controller.fault}.")
                exit_code = 4
                break

            readable, _, _ = select.select([fd], [], [], 0.1)
            if not readable:
                if time.monotonic() >= next_status_time:
                    print_status(*controller.status())
                    next_status_time = time.monotonic() + 0.25
                continue
            key = read_key(fd)
            if key in {"q", "escape"}:
                break
            if key == "up":
                controller.adjust_target(step, 0.0)
            elif key == "down":
                controller.adjust_target(-step, 0.0)
            elif key == "left":
                controller.adjust_target(0.0, step)
            elif key == "right":
                controller.adjust_target(0.0, -step)
            elif key in {"c", "0"}:
                controller.center_target()
            else:
                continue
            print_status(*controller.status())
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_terminal_settings)
        print("\nReleasing rt/arm_sdk neck control...")
        controller.release_and_close()

    print("Neck control released; locomotion mode was not changed.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
