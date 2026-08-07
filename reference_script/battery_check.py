#!/usr/bin/env python3
"""Print R1 battery status received from the Unitree DDS BMS topic."""

import argparse
import signal
import threading
import time
from typing import Iterable

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import BmsState_


DEFAULT_TOPIC = "rt/lf/bmsstate"


def nonzero(values: Iterable[int]) -> list[int]:
    """Return populated sensor values; unused BMS array entries are normally zero."""
    return [int(value) for value in values if value != 0]


class BatteryMonitor:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_print_time = 0.0
        self.message_count = 0

    def handle(self, msg: BmsState_) -> None:
        self.message_count += 1
        now = time.monotonic()
        if now - self.last_print_time < self.interval:
            return
        self.last_print_time = now

        pack_mv = nonzero(msg.bmsvoltage)
        cell_mv = nonzero(msg.cell_vol)
        temperatures = nonzero(msg.temperature)

        print("\n" + "=" * 62)
        print(time.strftime("Battery status  %Y-%m-%d %H:%M:%S"))
        print(f"Charge (SOC)   : {int(msg.soc)} %")
        print(f"Health (SOH)   : {int(msg.soh)} %")
        print(
            f"Current        : {int(msg.current)} mA "
            f"({msg.current / 1000.0:.3f} A)"
        )
        print(f"Cycle count    : {int(msg.cycle)}")
        print(
            "BMS version    : "
            f"{int(msg.version_high)}.{int(msg.version_low)}"
        )
        print(f"Function/state : fn={int(msg.fn)}, status={list(msg.bmsstate)}")

        if pack_mv:
            print(
                "Pack voltage   : "
                + ", ".join(f"{value} mV ({value / 1000.0:.3f} V)" for value in pack_mv)
            )
        else:
            print("Pack voltage   : no populated values")

        if cell_mv:
            print(f"Cell voltages  : {cell_mv} mV")
            print(
                "Cell summary   : "
                f"min={min(cell_mv)} mV, max={max(cell_mv)} mV, "
                f"spread={max(cell_mv) - min(cell_mv)} mV"
            )
        else:
            print("Cell voltages  : no populated values")

        # Keep temperature values raw because their scale is firmware-dependent.
        print(f"Temperatures   : {temperatures or 'no populated values'} (raw)")
        print(f"Messages seen  : {self.message_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Subscribe to the Unitree R1 BMS topic and print battery status."
    )
    parser.add_argument(
        "network_interface",
        help="Network interface connected to the robot, for example enp2s0",
    )
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"DDS topic (default: {DEFAULT_TOPIC})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Minimum seconds between terminal updates (default: 1.0)",
    )
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    return args


def main() -> None:
    args = parse_args()
    stop_event = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    ChannelFactoryInitialize(0, args.network_interface)
    monitor = BatteryMonitor(args.interval)
    subscriber = ChannelSubscriber(args.topic, BmsState_)
    subscriber.Init(monitor.handle, 10)

    print(f"Listening for battery data on {args.topic!r}...")
    print("Press Ctrl+C to stop.")
    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        subscriber.Close()
        print("\nBattery monitor stopped.")


if __name__ == "__main__":
    main()
