"""Live Unitree R1 battery telemetry from the DDS BMS topic."""

from __future__ import annotations

import os
import threading
import time
from typing import Iterable

from backend.unitree_dds import UNITREE_DDS_INIT_LOCK


DEFAULT_TOPIC = "rt/lf/bmsstate"
GOOD_BALANCE_MV = 30


def _nonzero(values: Iterable[int]) -> list[int]:
    """Remove unused zero-filled entries from Unitree BMS arrays."""
    return [int(value) for value in values if int(value) != 0]


class RobotBatteryService:
    """Subscribe once to the robot BMS and retain the latest normalized reading."""

    def __init__(
        self,
        network_interface: str | None = None,
        topic: str | None = None,
    ) -> None:
        self.network_interface = (
            network_interface or os.getenv("UNITREE_NETWORK_INTERFACE", "")
        ).strip()
        self.topic = (topic or os.getenv("UNITREE_BATTERY_TOPIC", DEFAULT_TOPIC)).strip()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._subscriber = None
        self._reading: dict[str, object] | None = None
        self._message_count = 0
        self._last_update_at: float | None = None
        self._state = "not_configured" if not self.network_interface else "stopped"
        self._error: str | None = None

    def start(self) -> None:
        with self._lock:
            if not self.network_interface:
                self._state = "not_configured"
                self._error = "UNITREE_NETWORK_INTERFACE is not configured."
                return
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._state = "connecting"
            self._error = None
            self._thread = threading.Thread(
                target=self._subscribe, name="unitree-battery", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        subscriber = self._subscriber
        if subscriber is not None:
            try:
                subscriber.Close()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)
        with self._lock:
            if self._state not in {"not_configured", "error"}:
                self._state = "stopped"

    def _subscribe(self) -> None:
        try:
            from unitree_sdk2py.core.channel import (
                ChannelFactoryInitialize,
                ChannelSubscriber,
            )
            from unitree_sdk2py.idl.unitree_hg.msg.dds_ import BmsState_
        except ImportError as exc:
            self._set_error(f"Unitree SDK could not be imported: {exc}")
            return

        retry_delay = 1.0
        while not self._stop_event.is_set():
            subscriber = None
            try:
                # The camera and battery share one process-wide DDS participant.
                # Serialize entity creation to avoid transient CycloneDDS topic
                # initialization failures during backend startup.
                with UNITREE_DDS_INIT_LOCK:
                    ChannelFactoryInitialize(0, self.network_interface)
                    subscriber = ChannelSubscriber(self.topic, BmsState_)
                    subscriber.Init(self._handle_message, 10)
                self._subscriber = subscriber
                with self._lock:
                    self._state = "waiting"
                    self._error = None
                self._stop_event.wait()
                break
            except Exception as exc:
                self._set_error(
                    f"Could not subscribe to battery data: {exc}",
                    state="reconnecting",
                )
                if self._stop_event.wait(retry_delay):
                    break
                retry_delay = min(retry_delay * 2.0, 10.0)
            finally:
                if subscriber is not None:
                    try:
                        subscriber.Close()
                    except Exception:
                        pass
                self._subscriber = None

    def _set_error(self, message: str, state: str = "error") -> None:
        with self._lock:
            self._state = state
            self._error = message

    def _handle_message(self, message: object) -> None:
        pack_mv = _nonzero(message.bmsvoltage)
        cell_mv = _nonzero(message.cell_vol)
        temperatures = _nonzero(message.temperature)
        current_ma = int(message.current)
        balance_mv = max(cell_mv) - min(cell_mv) if cell_mv else None

        charge_state = (
            "DISCHARGING" if current_ma < -50
            else "CHARGING" if current_ma > 50
            else "IDLE"
        )
        soh = int(message.soh)
        health = (
            "HEALTHY"
            if soh >= 80
            else "SERVICE SOON" if soh >= 60 else "SERVICE REQUIRED"
        )
        now = time.time()
        reading = {
            "charge_percent": int(message.soc),
            "health_percent": soh,
            "health": health,
            "voltage_v": round(pack_mv[0] / 1000.0, 3) if pack_mv else None,
            "current_a": round(current_ma / 1000.0, 3),
            "charge_state": charge_state,
            "max_temperature_c": max(temperatures) if temperatures else None,
            "cell_count": len(cell_mv),
            "cells": f"{len(cell_mv)}S" if cell_mv else None,
            "balance_mv": balance_mv,
            "balance": (
                "GOOD" if balance_mv is not None and balance_mv <= GOOD_BALANCE_MV
                else "CHECK" if balance_mv is not None else None
            ),
            "cycle_count": int(message.cycle),
            "bms_version": f"{int(message.version_high)}.{int(message.version_low)}",
            "updated_at": now,
        }
        with self._lock:
            self._reading = reading
            self._message_count += 1
            self._last_update_at = now
            self._state = "connected"
            self._error = None

    def status(self) -> dict[str, object]:
        with self._lock:
            age = (
                round(time.time() - self._last_update_at, 3)
                if self._last_update_at is not None else None
            )
            connected = self._state == "connected" and (age is None or age < 10)
            display_state = (
                "stale" if self._state == "connected" and not connected else self._state
            )
            return {
                "configured": bool(self.network_interface),
                "connected": connected,
                "state": display_state,
                "topic": self.topic,
                "last_update_age_seconds": age,
                "message_count": self._message_count,
                "error": self._error,
                "battery": dict(self._reading) if self._reading else None,
            }
