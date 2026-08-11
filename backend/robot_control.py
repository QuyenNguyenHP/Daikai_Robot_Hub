"""Bounded locomotion control for the Unitree R1."""

from __future__ import annotations

import json
import os
import threading
import time


COMMAND_DURATION = 1.0
LINEAR_SPEED = 0.5
LATERAL_SPEED = 0.4
TURN_SPEED = 0.8
LOCOMOTION_FSM_ID = 811
ARM_RELEASE_SETTLE_TIME = 8.0

NECK_ACTIONS = {"neck_up", "neck_down", "neck_left", "neck_right", "neck_center"}
ARM_ACTIONS = {
    "arm_blow_kiss_both": "blow_kiss_with_both_hands",
    "arm_blow_kiss_left": "blow_kiss_with_left_hand",
    "arm_blow_kiss_right": "blow_kiss_with_right_hand",
    "arm_both_hands_up": "both_hands_up",
    "arm_clap": "clamp",
    "arm_high_five": "high_five",
    "arm_hug": "hug",
    "arm_refuse": "refuse",
    "arm_right_hand_up": "right_hand_up",
    "arm_ultraman_ray": "ultraman_ray",
    "arm_wave_under_head": "wave_under_head",
    "arm_wave": "wave_above_head",
    "arm_handshake": "shake_hand",
    "arm_box_left_win": "box_left_hand_win",
    "arm_box_right_win": "box_right_hand_win",
    "arm_box_both_win": "box_both_hand_win",
    "arm_extend_right_arm": "extend_right_arm_forward",
    "arm_right_hand_heart": "right_hand_on_heart",
    "arm_hands_up_right": "both_hands_up_deviate_right",
    "arm_emphasize": "emphasize",
    "arm_forward_push": "forward_push",
    "arm_release": "release_arm",
}

FSM_NAMES = {
    0: "ZERO TORQUE",
    1: "DAMPING",
    4: "STANCE",
    701: "LIE TO STAND",
    702: "STAND TO LIE",
    811: "LOCOMOTION",
}

VELOCITY_COMMANDS = {
    "forward": (LINEAR_SPEED, 0.0, 0.0),
    "backward": (-LINEAR_SPEED, 0.0, 0.0),
    "left": (0.0, LATERAL_SPEED, 0.0),
    "right": (0.0, -LATERAL_SPEED, 0.0),
    "turn_left": (0.0, 0.0, TURN_SPEED),
    "turn_right": (0.0, 0.0, -TURN_SPEED),
}


class RobotControlError(RuntimeError):
    """Raised when the robot rejects or cannot execute a control command."""


class RobotControlBusyError(RobotControlError):
    """Raised when another control command is still running."""


class RobotControlStateError(RobotControlError):
    """Raised when a command is invalid for the current locomotion state."""


class RobotControlService:
    """Own one R1 LocoClient and execute short, serialized commands."""

    def __init__(self, network_interface: str | None = None) -> None:
        self.network_interface = (
            network_interface or os.getenv("UNITREE_NETWORK_INTERFACE", "")
        ).strip()
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._client = None
        self._arm_client = None
        self._arm_actions: dict[int, str] | None = None
        self._neck_controller = None
        self._locomotion_started = False
        self._last_action: str | None = None
        self._last_code: int | None = None
        self._error: str | None = None

    def status(self) -> dict[str, object]:
        with self._state_lock:
            return {
                "configured": bool(self.network_interface),
                "initialized": self._client is not None,
                "busy": self._lock.locked(),
                "locomotion_started": self._locomotion_started,
                "last_action": self._last_action,
                "last_code": self._last_code,
                "error": self._error,
                "command_duration_seconds": COMMAND_DURATION,
                "linear_speed_mps": LINEAR_SPEED,
                "lateral_speed_mps": LATERAL_SPEED,
                "turn_speed_radps": TURN_SPEED,
            }

    def _client_instance(self):
        if self._client is not None:
            return self._client
        if not self.network_interface:
            raise RobotControlError("UNITREE_NETWORK_INTERFACE is not configured.")

        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.r1.loco.r1_loco_client import LocoClient
        except ImportError as exc:
            raise RobotControlError(
                f"Unitree SDK could not be imported: {exc}"
            ) from exc

        try:
            ChannelFactoryInitialize(0, self.network_interface)
            client = LocoClient()
            client.SetTimeout(3.0)
            client.Init()
        except Exception as exc:
            raise RobotControlError(
                f"Could not initialize the Unitree locomotion client: {exc}"
            ) from exc

        self._client = client
        return client

    def _arm_client_instance(self):
        if self._arm_client is not None:
            return self._arm_client
        try:
            from unitree_sdk2py.g1.arm.g1_arm_action_client import G1ArmActionClient

            client = G1ArmActionClient()
            client.SetTimeout(10.0)
            client.Init()
        except Exception as exc:
            raise RobotControlError(
                f"Could not initialize the Unitree arm-action client: {exc}"
            ) from exc
        self._arm_client = client
        return client

    @staticmethod
    def _collect_arm_actions(value, actions: dict[int, str]) -> None:
        if isinstance(value, dict):
            if "id" in value and "name" in value:
                try:
                    actions[int(value["id"])] = str(value["name"])
                except (TypeError, ValueError):
                    pass
            for child in value.values():
                RobotControlService._collect_arm_actions(child, actions)
        elif isinstance(value, list):
            for child in value:
                RobotControlService._collect_arm_actions(child, actions)

    def _available_arm_actions(self) -> dict[int, str]:
        if self._arm_actions is not None:
            return self._arm_actions
        code, payload = self._arm_client_instance().GetActionList()
        self._require_success(code, "read arm action list")
        actions: dict[int, str] = {}
        self._collect_arm_actions(payload, actions)
        if not actions:
            raise RobotControlError("The robot returned an empty arm action list.")
        self._arm_actions = actions
        return actions

    def _execute_arm_action(self, action_name: str) -> int:
        action_id = next(
            (
                candidate_id
                for candidate_id, candidate_name in self._available_arm_actions().items()
                if candidate_name == action_name
            ),
            None,
        )
        if action_id is None:
            raise RobotControlError(
                f"Arm action '{action_name}' is not advertised by this robot."
            )
        code = self._arm_client_instance().ExecuteAction(action_id)
        self._require_success(code, action_name)
        return code

    def _release_neck(self) -> None:
        if self._neck_controller is not None:
            self._neck_controller.close()
            self._neck_controller = None

    def _neck_controller_instance(self):
        if self._neck_controller is not None:
            if self._neck_controller.fault is None:
                return self._neck_controller
            self._release_neck()
        try:
            from backend.robot_neck import RobotNeckController

            # Arm actions retain ownership after execution. Release that service
            # before claiming the same joints through rt/arm_sdk for neck control.
            self._execute_arm_action("release_arm")
            time.sleep(ARM_RELEASE_SETTLE_TIME)
            controller = RobotNeckController()
            controller.initialize()
            if not controller.start():
                controller.close()
                raise RobotControlError(
                    "Timed out waiting for robot joint feedback; neck control did not start."
                )
        except RobotControlError:
            raise
        except Exception as exc:
            raise RobotControlError(f"Could not initialize neck control: {exc}") from exc
        self._neck_controller = controller
        return controller

    @staticmethod
    def _fsm_id(client) -> int:
        try:
            from unitree_sdk2py.r1.loco.r1_loco_api import (
                ROBOT_API_ID_LOCO_GET_FSM_ID,
            )
        except ImportError as exc:
            raise RobotControlError(
                f"Unitree FSM API could not be imported: {exc}"
            ) from exc

        code, data = client._Call(ROBOT_API_ID_LOCO_GET_FSM_ID, "{}")
        if code != 0:
            raise RobotControlError(f"FSM mode query failed with code {code}.")
        try:
            return int(json.loads(data)["data"])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise RobotControlError(
                "The robot FSM mode response could not be decoded."
            ) from exc

    def _require_locomotion(self, client) -> None:
        with self._state_lock:
            locomotion_started = self._locomotion_started
        if not locomotion_started or self._fsm_id(client) != LOCOMOTION_FSM_ID:
            raise RobotControlStateError(
                "Enable locomotion before sending robot control commands."
            )

    @staticmethod
    def _require_success(code: int, action: str) -> None:
        if code != 0:
            raise RobotControlError(
                f"Robot rejected {action.replace('_', ' ')} with code {code}."
            )

    def _set_result(
        self,
        action: str,
        code: int | None = None,
        error: str | None = None,
    ) -> None:
        with self._state_lock:
            self._last_action = action
            self._last_code = code
            self._error = error

    def execute(self, action: str) -> dict[str, object]:
        if not self._lock.acquire(blocking=False):
            raise RobotControlBusyError("Another robot control command is running.")

        try:
            client = self._client_instance()

            if action == "stance":
                with self._state_lock:
                    locomotion_started = self._locomotion_started
                if locomotion_started:
                    # Some R1 firmware returns 127 for this best-effort stop
                    # while still accepting the following FSM transition.
                    client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                self._release_neck()
                code = client.SetFsmId(4)
                self._require_success(code, "enter stance mode")
                with self._state_lock:
                    self._locomotion_started = False

            elif action == "zero_torque":
                self._release_neck()
                code = client.SetFsmId(0)
                self._require_success(code, "enter zero torque mode")
                with self._state_lock:
                    self._locomotion_started = False

            elif action == "enable":
                code = client.SetFsmId(4)
                self._require_success(code, "enter stance mode")
                time.sleep(0.5)
                code = client.SetFsmId(811)
                self._require_success(code, "enable locomotion")
                with self._state_lock:
                    self._locomotion_started = True

            elif action == "disable":
                self._release_neck()
                code = client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                self._require_success(code, "disable control")
                code = client.SetFsmId(4)
                self._require_success(code, "return to stance mode")
                with self._state_lock:
                    self._locomotion_started = False

            elif action == "stop":
                self._require_locomotion(client)
                code = client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                self._require_success(code, action)

            elif action in VELOCITY_COMMANDS:
                self._require_locomotion(client)
                vx, vy, omega = VELOCITY_COMMANDS[action]
                code = client.SetVelocity(vx, vy, omega, COMMAND_DURATION)
                self._require_success(code, action)

            elif action in NECK_ACTIONS:
                self._require_locomotion(client)
                self._neck_controller_instance().apply(action)
                code = 0

            elif action in ARM_ACTIONS:
                self._require_locomotion(client)
                self._release_neck()
                action_name = ARM_ACTIONS[action]
                code = self._execute_arm_action(action_name)

            else:
                raise RobotControlError(f"Unsupported robot action: {action}")

            self._set_result(action, code=code)
        except RobotControlError as exc:
            self._set_result(action, error=str(exc))
            raise
        except Exception as exc:
            message = f"Robot control failed: {exc}"
            self._set_result(action, error=message)
            raise RobotControlError(message) from exc
        finally:
            self._lock.release()
        return {"ok": True, "action": action, **self.status()}

    def mode(self) -> dict[str, object]:
        """Query the robot's registered FSM mode through locomotion API 7001."""
        if not self._lock.acquire(timeout=1.0):
            raise RobotControlBusyError("Robot control is busy; mode is unavailable.")

        try:
            client = self._client_instance()
            fsm_id = self._fsm_id(client)
            locomotion_active = fsm_id == LOCOMOTION_FSM_ID
            with self._state_lock:
                self._locomotion_started = locomotion_active
            if not locomotion_active:
                self._release_neck()

            fsm_name = FSM_NAMES.get(fsm_id, "UNKNOWN/UNDOCUMENTED")
            return {
                "configured": bool(self.network_interface),
                "fsm_id": fsm_id,
                "fsm_name": fsm_name,
                "display": f"{fsm_name} (ID {fsm_id})",
            }
        except RobotControlError:
            raise
        except Exception as exc:
            raise RobotControlError(f"FSM mode query failed: {exc}") from exc
        finally:
            self._lock.release()

    def stop(self) -> None:
        """Send a final stop during shutdown when the client was initialized."""
        client = self._client
        self._release_neck()
        if client is None:
            return
        with self._lock:
            try:
                client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
            except Exception:
                pass
