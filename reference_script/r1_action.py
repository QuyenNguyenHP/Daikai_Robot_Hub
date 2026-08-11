#!/usr/bin/env python3
"""List and execute actions advertised by the Unitree R1 ``arm`` service."""

import argparse
import json
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient
from unitree_sdk2py.r1.loco.r1_loco_api import ROBOT_API_ID_LOCO_GET_FSM_ID
from unitree_sdk2py.r1.loco.r1_loco_client import LocoClient


LOCOMOTION_FSM_ID = 811

# Friendly names accepted in addition to the exact names returned by firmware.
ALIASES = {
    "clap": "clamp",  # The current R1 firmware advertises this name as "clamp".
    "handshake": "shake_hand",
    "handshake-1": "shake_hand",
    "release": "release_arm",
    "wave": "wave_above_head",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or execute an action advertised by the R1 arm service."
    )
    parser.add_argument(
        "network_interface",
        help="Network interface connected to the robot, for example eth10",
    )
    parser.add_argument(
        "action",
        nargs="?",
        help="Action name, action ID, alias (wave/handshake/clap/release), or list",
    )
    parser.add_argument(
        "--start-locomotion",
        action="store_true",
        help="Explicitly switch to locomotion (FSM 811) before executing an action",
    )
    parser.add_argument(
        "--settle-time",
        type=float,
        default=3.0,
        help="Seconds to wait after entering locomotion (default: 3.0)",
    )
    parser.add_argument(
        "--action-wait",
        type=float,
        default=8.0,
        help="Seconds to wait before accepting the next action (default: 8.0)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="RPC timeout in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive safety confirmation",
    )
    args = parser.parse_args()

    if args.settle_time < 0:
        parser.error("--settle-time cannot be negative")
    if args.action_wait < 0:
        parser.error("--action-wait cannot be negative")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return args


def collect_actions(value, actions: dict) -> None:
    """Collect action IDs and names from the arm service's nested response."""
    if isinstance(value, dict):
        if "id" in value and "name" in value:
            try:
                actions[int(value["id"])] = str(value["name"])
            except (TypeError, ValueError):
                pass
        for child in value.values():
            collect_actions(child, actions)
    elif isinstance(value, list):
        for child in value:
            collect_actions(child, actions)


def get_available_actions(client: G1ArmActionClient):
    code, payload = client.GetActionList()
    if code != 0 or payload is None:
        return code, {}

    actions = {}
    collect_actions(payload, actions)
    return code, actions


def print_actions(actions: dict) -> None:
    print("Available actions advertised by the R1 arm service:")
    for action_id, name in sorted(actions.items()):
        aliases = sorted(alias for alias, target in ALIASES.items() if target == name)
        alias_text = f"  aliases: {', '.join(aliases)}" if aliases else ""
        print(f"  {action_id:>2}  {name}{alias_text}")


def resolve_action(value: str, actions: dict):
    try:
        action_id = int(value)
    except ValueError:
        requested_name = ALIASES.get(value.lower(), value)
        for action_id, name in actions.items():
            if name == requested_name:
                return action_id, name
        return None, None

    return action_id, actions.get(action_id)


def get_fsm_id(client: LocoClient):
    """Query R1 API 7001, which the client registers without a public wrapper."""
    code, data = client._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
    if code != 0:
        return code, None

    try:
        payload = json.loads(data)
        return code, int(payload["data"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return code, None


def confirm(action_id: int, action_name: str, start_locomotion: bool) -> bool:
    print("WARNING: This command will move the real robot.")
    print("Secure the robot and keep people and objects away from both arms.")
    print("Keep the remote controller ready for emergency damping/stop.")
    if start_locomotion:
        print("The script will also request locomotion mode (FSM 811).")
    answer = input(
        f"Type YES to execute action {action_id} '{action_name}': "
    ).strip()
    return answer == "YES"


def confirm_interactive(start_locomotion: bool) -> bool:
    print("WARNING: Interactive mode can repeatedly move the real robot.")
    print("Secure the robot and keep people and objects away from both arms.")
    print("Keep the remote controller ready for emergency damping/stop.")
    if start_locomotion:
        print("The script will also request locomotion mode (FSM 811).")
    return input("Type YES to enable interactive action execution: ").strip() == "YES"


def ensure_locomotion(args: argparse.Namespace) -> int:
    loco_client = LocoClient()
    loco_client.SetTimeout(args.timeout)
    loco_client.Init()

    code, fsm_id = get_fsm_id(loco_client)
    if code != 0 or fsm_id is None:
        print(f"Cannot verify the R1 FSM (RPC code {code}); no action was sent.")
        return 2

    print(f"Current FSM: {fsm_id}")
    if fsm_id == LOCOMOTION_FSM_ID:
        return 0

    if not args.start_locomotion:
        print(
            "The robot is not in locomotion mode (FSM 811). Enter locomotion "
            "first or rerun with --start-locomotion."
        )
        return 3

    print("Requesting locomotion mode (FSM 811)...")
    code = loco_client.SetFsmId(LOCOMOTION_FSM_ID)
    print(f"SetFsmId result: {code}")
    if code != 0:
        print("Locomotion request failed; no action was sent.")
        return 4

    time.sleep(args.settle_time)
    code, fsm_id = get_fsm_id(loco_client)
    if code != 0 or fsm_id != LOCOMOTION_FSM_ID:
        print(
            f"Locomotion could not be verified (RPC code {code}, FSM {fsm_id}); "
            "no action was sent."
        )
        return 5

    return 0


def execute_action(
    client: G1ArmActionClient,
    action_id: int,
    action_name: str,
    action_wait: float,
) -> int:
    print(f"Executing arm action {action_id}: {action_name}...")
    code = client.ExecuteAction(action_id)
    print(f"ExecuteAction({action_id}) result: {code}")
    if code != 0:
        print("The robot rejected or could not receive the arm action.")
        return 6

    if action_name == "release_arm":
        print(
            "release_arm was accepted. It releases/returns arm-action control and "
            "may not produce a visible gesture."
        )
    else:
        print("Arm action accepted.")

    if action_wait > 0:
        print(
            f"Waiting {action_wait:g} seconds before accepting another action "
            "(the arm service does not report completion state)..."
        )
        time.sleep(action_wait)
    print("Ready for the next action.")
    return 0


def interactive_loop(
    args: argparse.Namespace,
    arm_client: G1ArmActionClient,
    actions: dict,
) -> int:
    print_actions(actions)
    print("Commands: enter an action ID/name, 'list' to show actions, or 'q' to quit.")

    if not args.yes and not confirm_interactive(args.start_locomotion):
        print("Cancelled; no action command was sent.")
        return 1

    result = ensure_locomotion(args)
    if result != 0:
        return result

    while True:
        try:
            value = input("\nAction ID or name [list/q]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive action mode.")
            return 0

        if not value:
            continue
        if value.lower() in {"q", "quit", "exit"}:
            print("Exiting interactive action mode.")
            return 0
        if value.lower() == "list":
            print_actions(actions)
            continue

        action_id, action_name = resolve_action(value, actions)
        if action_name is None:
            print(f"Action {value!r} is not advertised by this R1 firmware.")
            continue

        execute_action(
            arm_client,
            action_id,
            action_name,
            args.action_wait,
        )


def main() -> int:
    args = parse_args()
    ChannelFactoryInitialize(0, args.network_interface)

    # The class is named for G1 in this SDK, but R1 firmware advertises the same
    # generic "arm" RPC service and returns its own model-specific action list.
    arm_client = G1ArmActionClient()
    arm_client.SetTimeout(args.timeout)
    arm_client.Init()

    code, actions = get_available_actions(arm_client)
    if code != 0:
        print(f"Cannot read the R1 arm-action list (RPC code {code}).")
        return 1
    if not actions:
        print("The R1 arm service returned an empty action list.")
        return 1

    if args.action is None:
        return interactive_loop(args, arm_client, actions)

    if args.action.lower() == "list":
        print_actions(actions)
        return 0

    action_id, action_name = resolve_action(args.action, actions)
    if action_name is None:
        print(f"Action {args.action!r} is not advertised by this R1 firmware.")
        print_actions(actions)
        return 1

    if not args.yes and not confirm(action_id, action_name, args.start_locomotion):
        print("Cancelled; no action command was sent.")
        return 1

    result = ensure_locomotion(args)
    if result != 0:
        return result

    return execute_action(
        arm_client,
        action_id,
        action_name,
        args.action_wait,
    )


if __name__ == "__main__":
    sys.exit(main())
