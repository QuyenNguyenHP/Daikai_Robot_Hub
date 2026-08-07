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

            if action == "enable":
                code = client.SetFsmId(4)
                self._require_success(code, "enter stance mode")
                time.sleep(0.5)
                code = client.SetFsmId(811)
                self._require_success(code, "enable locomotion")
                with self._state_lock:
                    self._locomotion_started = True

            elif action == "disable":
                code = client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                self._require_success(code, "disable control")
                code = client.SetFsmId(4)
                self._require_success(code, "return to stance mode")
                with self._state_lock:
                    self._locomotion_started = False

            elif action == "stop":
                code = client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
                self._require_success(code, action)

            elif action in VELOCITY_COMMANDS:
                with self._state_lock:
                    locomotion_started = self._locomotion_started
                if not locomotion_started:
                    raise RobotControlStateError(
                        "Enable locomotion before sending movement commands."
                    )
                vx, vy, omega = VELOCITY_COMMANDS[action]
                code = client.SetVelocity(vx, vy, omega, COMMAND_DURATION)
                self._require_success(code, action)

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
                fsm_id = int(json.loads(data)["data"])
            except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                raise RobotControlError(
                    "The robot FSM mode response could not be decoded."
                ) from exc

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
        if client is None:
            return
        with self._lock:
            try:
                client.SetVelocity(0.0, 0.0, 0.0, COMMAND_DURATION)
            except Exception:
                pass
