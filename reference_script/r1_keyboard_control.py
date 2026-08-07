#!/usr/bin/env python3
"""Control Unitree R1 locomotion and posture actions from a terminal."""

import argparse
import select
import signal
import sys
import termios
import time
import tty

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.r1.loco.r1_loco_client import LocoClient


# The R1 reference client sends one-second Move commands. Some R1 firmware
# rejects fractional durations (observed response code: 127).
COMMAND_DURATION = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keyboard controller for Unitree R1")
    parser.add_argument(
        "network_interface",
        help="Network interface connected to the robot, for example enp2s0",
    )
    parser.add_argument(
        "--linear-speed",
        type=float,
        default=0.5,
        help="Forward/backward speed in m/s (default: 0.5)",
    )
    parser.add_argument(
        "--turn-speed",
        type=float,
        default=0.8,
        help="Turning speed in rad/s (default: 0.8)",
    )
    parser.add_argument(
        "--lateral-speed",
        type=float,
        default=0.4,
        help="Left/right speed in m/s (default: 0.4)",
    )
    args = parser.parse_args()

    if not 0.0 < args.linear_speed <= 1.0:
        parser.error("--linear-speed must be greater than 0 and at most 1.0")
    if not 0.0 < args.turn_speed <= 1.5:
        parser.error("--turn-speed must be greater than 0 and at most 1.5")
    if not 0.0 < args.lateral_speed <= 1.0:
        parser.error("--lateral-speed must be greater than 0 and at most 1.0")
    if not sys.stdin.isatty():
        parser.error("keyboard control requires an interactive terminal")
    return args


def print_controls(linear_speed: float, lateral_speed: float, turn_speed: float) -> None:
    print("\nControls (lowercase or uppercase):")
    print("  P       enter locomotion mode")
    print(f"  W / S   forward / backward ({linear_speed:.2f} m/s)")
    print(f"  A / D   move left / right ({lateral_speed:.2f} m/s)")
    print(f"  R / E   turn left / right ({turn_speed:.2f} rad/s)")
    print("  L       lie to stand")
    print("  K       stand to lie")
    print("  Space/X stop immediately")
    print("  Q/ESC   stop and quit")
    print("\nEach movement key requests one second of motion; Space/X stops early.")


def send_velocity(
    client: LocoClient, vx: float, vy: float, omega: float, label: str
) -> None:
    code = client.SetVelocity(vx, vy, omega, COMMAND_DURATION)
    if code == 0:
        print(
            f"\rCommand: {label:<10} "
            f"vx={vx:+.2f}, vy={vy:+.2f} m/s, "
            f"omega={omega:+.2f} rad/s   ",
            end="",
            flush=True,
        )
    else:
        print(f"\nCommand {label!r} failed with code {code}")


def main() -> int:
    args = parse_args()

    print("WARNING: The robot can move and turn while this program is running.")
    print("Use a flat, clear area and keep an emergency stop available.")
    confirmation = input("Type MOVE to continue: ").strip()
    if confirmation != "MOVE":
        print("Cancelled; no motion command was sent.")
        return 1

    ChannelFactoryInitialize(0, args.network_interface)
    client = LocoClient()
    client.SetTimeout(3.0)
    client.Init()

    should_stop = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal should_stop
        should_stop = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    old_terminal_settings = termios.tcgetattr(sys.stdin)
    locomotion_started = False
    print_controls(args.linear_speed, args.lateral_speed, args.turn_speed)

    try:
        tty.setcbreak(sys.stdin.fileno())

        while not should_stop:
            readable, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not readable:
                continue

            key = sys.stdin.read(1).lower()

            if key == "p":
                stance_code = client.SetFsmId(4)
                if stance_code != 0:
                    print(f"\nFailed to enter stance mode: code {stance_code}")
                    continue
                time.sleep(0.5)
                start_code = client.SetFsmId(811)
                if start_code == 0:
                    locomotion_started = True
                    print("\rLocomotion mode started.                     ")
                else:
                    print(f"\nFailed to start locomotion: code {start_code}")
                continue

            if key in {"q", "\x1b"}:
                break

            if key in {" ", "x"}:
                client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                print("\rCommand: STOP        ", end="", flush=True)
                continue

            if key == "l":
                client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                print("\rAction: LIE TO STAND (starting in 3 seconds)       ")
                stance_code = client.SetFsmId(4)
                if stance_code != 0:
                    print(f"Failed to enter stance mode: code {stance_code}")
                    continue
                time.sleep(3.0)
                action_code = client.SetFsmId(701)
                locomotion_started = False
                if action_code == 0:
                    print("Action: Lie2StandUp started. Press P before walking.")
                else:
                    print(f"Action Lie2StandUp failed: code {action_code}")
                continue

            if key == "k":
                client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                action_code = client.SetFsmId(702)
                locomotion_started = False
                if action_code == 0:
                    print("\rAction: StandUp2Lie started.                    ")
                else:
                    print(f"\nAction StandUp2Lie failed: code {action_code}")
                continue

            if key not in {"w", "s", "a", "d", "r", "e"}:
                continue

            if not locomotion_started:
                print("\rPress P to enter locomotion mode first.     ", end="", flush=True)
                continue

            if key == "w":
                send_velocity(client, args.linear_speed, 0.0, 0.0, "FORWARD")
            elif key == "s":
                send_velocity(client, -args.linear_speed, 0.0, 0.0, "BACKWARD")
            elif key == "a":
                send_velocity(client, 0.0, args.lateral_speed, 0.0, "MOVE LEFT")
            elif key == "d":
                send_velocity(client, 0.0, -args.lateral_speed, 0.0, "MOVE RIGHT")
            elif key == "r":
                send_velocity(client, 0.0, 0.0, args.turn_speed, "TURN LEFT")
            elif key == "e":
                send_velocity(client, 0.0, 0.0, -args.turn_speed, "TURN RIGHT")
    finally:
        # Restore the terminal even if a DDS call or keyboard handler fails.
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_terminal_settings)
        try:
            client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
        except Exception as exc:
            print(f"\nWarning: final stop command failed: {exc}")

    print("\nRobot stopped. Keyboard controller exited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
