#!/usr/bin/env python3
"""List or switch R1 services through the Unitree robot_state DDS API.

This is an experimental R1 use of the generic Unitree robot_state protocol.
Always run ``list`` first and use the exact service name returned by the robot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow this utility to run directly from its own folder without requiring the
# SDK package to be installed site-wide.
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.robot_state.robot_state_api import (
    ROBOT_STATE_ERR_SERVICE_PROTECTED,
)
from unitree_sdk2py.go2.robot_state.robot_state_client import RobotStateClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("network_interface", help="interface connected to the R1")
    parser.add_argument("action", choices=("list", "on", "off"))
    parser.add_argument(
        "service",
        nargs="?",
        help="exact service name returned by the list action",
    )
    return parser.parse_args()


def get_services(client: RobotStateClient):
    code, services = client.ServiceList()
    if code != 0 or services is None:
        raise RuntimeError(f"ServiceList failed with code {code}")
    return services


def main() -> int:
    args = parse_args()
    if args.action != "list" and not args.service:
        raise SystemExit("on/off requires the exact service name from list")

    print(f"DDS interface: {args.network_interface}")
    ChannelFactoryInitialize(0, args.network_interface)
    client = RobotStateClient()
    client.SetTimeout(3.0)
    client.Init()

    services = get_services(client)
    if args.action == "list":
        print(f"{'SERVICE':<42} {'STATUS':<8} PROTECTED")
        for service in sorted(services, key=lambda item: item.name.lower()):
            print(
                f"{service.name:<42} {service.status!s:<8} "
                f"{'yes' if service.protect else 'no'}"
            )
        return 0

    matching = [service for service in services if service.name == args.service]
    if not matching:
        available = ", ".join(service.name for service in services)
        raise SystemExit(
            f"Service {args.service!r} was not returned by the robot. "
            f"Available services: {available}"
        )
    service = matching[0]
    if service.protect:
        raise SystemExit(
            f"Service {service.name!r} is protected and cannot be switched "
            "through this public API."
        )

    enable = args.action == "on"
    code = client.ServiceSwitch(service.name, enable)
    if code == ROBOT_STATE_ERR_SERVICE_PROTECTED:
        raise SystemExit(f"Robot reports that {service.name!r} is protected")
    if code != 0:
        raise SystemExit(f"ServiceSwitch failed with code {code}")

    refreshed = get_services(client)
    state = next((item for item in refreshed if item.name == service.name), None)
    print(
        f"Requested {service.name}: {'ON' if enable else 'OFF'}; "
        f"reported status={state.status if state is not None else 'unknown'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
