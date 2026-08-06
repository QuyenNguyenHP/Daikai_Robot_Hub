from __future__ import annotations

import os
import threading
import time
from typing import Iterator


class RobotCameraError(RuntimeError):
    """Raised when a frame cannot be obtained from the Unitree camera."""


class RobotCameraService:
    """Own one Unitree VideoClient and retain its newest JPEG frame."""

    def __init__(self, network_interface: str | None = None) -> None:
        self.network_interface = (
            network_interface or os.getenv("UNITREE_NETWORK_INTERFACE", "")
        ).strip()
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_jpeg: bytes | None = None
        self._frame_sequence = 0
        self._last_frame_at: float | None = None
        self._state = "not_configured" if not self.network_interface else "stopped"
        self._error: str | None = None

    def start(self) -> None:
        with self._condition:
            if not self.network_interface:
                self._state = "not_configured"
                self._error = (
                    "Set UNITREE_NETWORK_INTERFACE to the interface connected "
                    "to the robot (for example eth0)."
                )
                raise RobotCameraError(self._error)
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._state = "connecting"
            self._error = None
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="unitree-camera",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=4.0)
        with self._condition:
            if self._state not in {"not_configured", "error"}:
                self._state = "stopped"

    def _set_error(self, message: str, terminal: bool = False) -> None:
        with self._condition:
            self._error = message
            self._state = "error" if terminal else "reconnecting"
            self._condition.notify_all()

    def _capture_loop(self) -> None:
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.go2.video.video_client import VideoClient
        except ImportError:
            self._set_error(
                "unitree_sdk2py is not installed in the backend environment.",
                terminal=True,
            )
            return

        try:
            ChannelFactoryInitialize(0, self.network_interface)
            client = VideoClient()
            client.SetTimeout(3.0)
            client.Init()
        except Exception as exc:
            self._set_error(f"Could not initialize the Unitree camera: {exc}", terminal=True)
            return

        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                code, data = client.GetImageSample()
                if code != 0:
                    raise RobotCameraError(f"GetImageSample returned code {code}")
                jpeg = bytes(data)
                if not jpeg:
                    raise RobotCameraError("The robot returned an empty camera frame")
            except Exception as exc:
                consecutive_errors += 1
                self._set_error(f"Robot camera read failed: {exc}")
                if self._stop_event.wait(min(0.1 * consecutive_errors, 1.0)):
                    break
                continue

            consecutive_errors = 0
            with self._condition:
                self._latest_jpeg = jpeg
                self._frame_sequence += 1
                self._last_frame_at = time.time()
                self._state = "connected"
                self._error = None
                self._condition.notify_all()

    def status(self) -> dict[str, object]:
        with self._condition:
            age = (
                round(time.time() - self._last_frame_at, 3)
                if self._last_frame_at is not None
                else None
            )
            return {
                "configured": bool(self.network_interface),
                "network_interface": self.network_interface or None,
                "state": self._state,
                "connected": self._state == "connected",
                "frame_sequence": self._frame_sequence,
                "last_frame_age_seconds": age,
                "error": self._error,
            }

    def snapshot(self) -> tuple[bytes, int]:
        with self._condition:
            if self._latest_jpeg is None:
                message = self._error or "No robot camera frame is available yet."
                raise RobotCameraError(message)
            return self._latest_jpeg, self._frame_sequence

    def wait_for_frame(
        self, after_sequence: int, timeout: float = 5.0
    ) -> tuple[bytes | None, int]:
        with self._condition:
            self._condition.wait_for(
                lambda: self._frame_sequence > after_sequence
                or self._stop_event.is_set()
                or self._state == "error",
                timeout=timeout,
            )
            if self._latest_jpeg is None or self._frame_sequence <= after_sequence:
                return None, after_sequence
            return self._latest_jpeg, self._frame_sequence

    def mjpeg_stream(self) -> Iterator[bytes]:
        sequence = -1
        while not self._stop_event.is_set():
            jpeg, sequence = self.wait_for_frame(sequence)
            if jpeg is None:
                if self._state == "error":
                    break
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: "
                + str(len(jpeg)).encode("ascii")
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
