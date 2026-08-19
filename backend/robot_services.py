"""List and switch Unitree R1 services through the robot-state DDS API."""

from __future__ import annotations

import os
import threading

from backend.unitree_dds import UNITREE_DDS_INIT_LOCK


class RobotServiceError(RuntimeError):
    """Raised when robot services cannot be read or changed."""


class RobotServiceBusyError(RobotServiceError):
    """Raised when another service request is still running."""


class RobotServiceProtectedError(RobotServiceError):
    """Raised when a protected service is selected."""


class RobotServiceManager:
    """Own one RobotStateClient and serialize service list/switch requests."""

    def __init__(self, network_interface: str | None = None) -> None:
        self.network_interface = (
            network_interface or os.getenv("UNITREE_NETWORK_INTERFACE", "")
        ).strip()
        self._client = None
        self._lock = threading.Lock()
        self.status_inverted = os.getenv(
            "UNITREE_SERVICE_STATUS_INVERTED", "1"
        ).strip().lower() not in {"0", "false", "no", "off"}

    def _client_instance(self):
        if self._client is not None:
            return self._client
        if not self.network_interface:
            raise RobotServiceError("UNITREE_NETWORK_INTERFACE is not configured.")

        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.go2.robot_state.robot_state_client import (
                RobotStateClient,
            )
        except ImportError as exc:
            raise RobotServiceError(
                f"Unitree SDK could not be imported: {exc}"
            ) from exc

        try:
            with UNITREE_DDS_INIT_LOCK:
                ChannelFactoryInitialize(0, self.network_interface)
                client = RobotStateClient()
                client.SetTimeout(3.0)
                client.Init()
        except Exception as exc:
            raise RobotServiceError(
                f"Could not initialize the Unitree robot-state client: {exc}"
            ) from exc

        self._client = client
        return client

    def _normalize(self, services) -> list[dict[str, object]]:
        normalized = []
        for item in sorted(services, key=lambda value: value.name.lower()):
            try:
                raw_status = int(item.status)
            except (TypeError, ValueError):
                raw_status = 1 if bool(item.status) else 0
            normalized.append(
                {
                    "name": str(item.name),
                    # This R1 firmware reports 0 for a running service and 1
                    # for a stopped service. Keep this configurable for other
                    # Unitree firmware variants.
                    "enabled": not bool(raw_status)
                    if self.status_inverted
                    else bool(raw_status),
                    "raw_status": raw_status,
                    "protected": bool(item.protect),
                }
            )
        return normalized

    def _service_list(self, client) -> list[dict[str, object]]:
        try:
            code, services = client.ServiceList()
        except Exception as exc:
            raise RobotServiceError(f"Could not read robot services: {exc}") from exc
        if code != 0 or services is None:
            raise RobotServiceError(f"ServiceList failed with code {code}.")
        return self._normalize(services)

    def list(self) -> dict[str, object]:
        if not self._lock.acquire(blocking=False):
            raise RobotServiceBusyError("Another robot service request is in progress.")
        try:
            services = self._service_list(self._client_instance())
            return {
                "configured": True,
                "status_inverted": self.status_inverted,
                "count": len(services),
                "services": services,
            }
        finally:
            self._lock.release()

    def switch(self, name: str, enabled: bool) -> dict[str, object]:
        if not self._lock.acquire(blocking=False):
            raise RobotServiceBusyError("Another robot service request is in progress.")
        try:
            client = self._client_instance()
            services = self._service_list(client)
            selected = next((item for item in services if item["name"] == name), None)
            if selected is None:
                raise RobotServiceError(
                    f"Service {name!r} was not returned by the robot."
                )
            if selected["protected"]:
                raise RobotServiceProtectedError(
                    f"Service {name!r} is protected and cannot be switched."
                )

            try:
                code = client.ServiceSwitch(name, enabled)
            except Exception as exc:
                raise RobotServiceError(
                    f"Could not switch service {name!r}: {exc}"
                ) from exc

            try:
                from unitree_sdk2py.go2.robot_state.robot_state_api import (
                    ROBOT_STATE_ERR_SERVICE_PROTECTED,
                )
            except ImportError:
                ROBOT_STATE_ERR_SERVICE_PROTECTED = None

            if code == ROBOT_STATE_ERR_SERVICE_PROTECTED:
                raise RobotServiceProtectedError(
                    f"Robot reports that service {name!r} is protected."
                )
            if code != 0:
                raise RobotServiceError(f"ServiceSwitch failed with code {code}.")

            refreshed = self._service_list(client)
            current = next((item for item in refreshed if item["name"] == name), None)
            return {
                "configured": True,
                "status_inverted": self.status_inverted,
                "count": len(refreshed),
                "services": refreshed,
                "changed": current,
            }
        finally:
            self._lock.release()
