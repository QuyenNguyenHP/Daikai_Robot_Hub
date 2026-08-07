"""  """#!/usr/bin/env python3
"""Print the Unitree R1 operating mode and motion state periodically."""

import argparse
import json
import signal
import threading
from typing import Optional

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import SportModeState_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.r1.loco.r1_loco_api import ROBOT_API_ID_LOCO_GET_FSM_ID
from unitree_sdk2py.r1.loco.r1_loco_client import LocoClient


FSM_NAMES = {
    0: "ZERO TORQUE",
    1: "DAMPING",
    4: "STANCE",
    701: "LIE TO STAND",
    702: "STAND TO LIE",
    811: "LOCOMOTION",
}


class ModeMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sport_state: Optional[SportModeState_] = None
        self._low_state: Optional[LowState_] = None

    def handle_sport_state(self, msg: SportModeState_) -> None:
        with self._lock:
            self._sport_state = msg

    def handle_low_state(self, msg: LowState_) -> None:
        with self._lock:
            self._low_state = msg

    def snapshot(self):
        with self._lock:
            return self._sport_state, self._low_state


def get_fsm_id(client: LocoClient):
    """Query API 7001, which R1 registers but does not expose as a method."""
    code, data = client._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
    if code != 0:
        return code, None

    try:
        payload = json.loads(data)
        return code, int(payload["data"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return code, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print the Unitree R1 mode and motion state every five seconds."
    )
    parser.add_argument(
        "network_interface",
        help="Network interface connected to the robot, for example enp2s0",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between status reports (default: 5.0)",
    )
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    return args


def main() -> int:
    args = parse_args()
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    ChannelFactoryInitialize(0, args.network_interface)

    client = LocoClient()
    client.SetTimeout(3.0)
    client.Init()

    monitor = ModeMonitor()
    sport_subscriber = ChannelSubscriber("rt/sportmodestate", SportModeState_)
    sport_subscriber.Init(monitor.handle_sport_state, 10)
    low_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
    low_subscriber.Init(monitor.handle_low_state, 10)

    print(f"Checking R1 mode every {args.interval:g} seconds. Press Ctrl+C to stop.")

    try:
        while not stop_event.is_set():
            code, fsm_id = get_fsm_id(client)
            sport_state, low_state = monitor.snapshot()

            print("\n" + "=" * 60)
            if code == 0 and fsm_id is not None:
                fsm_name = FSM_NAMES.get(fsm_id, "UNKNOWN/UNDOCUMENTED")
                print(f"FSM mode       : {fsm_name} (ID {fsm_id})")
            elif code == 0:
                print("FSM mode       : response could not be decoded")
            else:
                print(f"FSM mode       : query failed with code {code}")

            if sport_state is None:
                print("Sport state    : waiting for rt/sportmodestate")
            else:
                velocity = [float(value) for value in sport_state.velocity]
                print(f"Sport mode raw : {int(sport_state.mode)}")
                print(f"Gait type raw  : {int(sport_state.gait_type)}")
                print(f"Velocity       : {velocity} m/s")
                print(f"Yaw speed      : {float(sport_state.yaw_speed):.3f} rad/s")
                print(f"Error code     : {int(sport_state.error_code)}")

            if low_state is None:
                print("Low state      : waiting for rt/lowstate")
            else:
                print(f"Mode machine   : {int(low_state.mode_machine)}")
                print(f"Mode PR        : {int(low_state.mode_pr)}")

            stop_event.wait(args.interval)
    finally:
        sport_subscriber.Close()
        low_subscriber.Close()

    print("\nMode monitor stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
