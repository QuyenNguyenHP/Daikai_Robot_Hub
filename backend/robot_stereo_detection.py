"""Web-facing YOLO-World object detection and stereo distance service."""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


BACKEND_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = Path(
    os.getenv(
        "R1_STEREO_SOURCE_DIR",
        "/home/r1-edu/unitree_sdk2_python/my_script/r1_yolo_world_stereo",
    )
)
DEFAULT_CLASSES = "person,chair,bottle,cup,table,door,box"
DETECTION_COLORS = (
    (80, 220, 120),
    (255, 180, 70),
    (80, 190, 255),
    (220, 100, 255),
    (70, 230, 230),
    (255, 120, 120),
    (180, 120, 255),
    (120, 255, 210),
)


class RobotStereoError(RuntimeError):
    """Raised when the stereo detection pipeline cannot be controlled."""


class RobotStereoStateError(RobotStereoError):
    """Raised when configuration changes require the pipeline to be stopped."""


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def _object_distance(
    points_3d: np.ndarray,
    disparity: np.ndarray,
    box: tuple[int, int, int, int],
    inner_scale: float,
    min_distance_m: float,
    max_distance_m: float,
    mode: str,
) -> float | None:
    """Use the robust inner-box median calculation from the reference script."""
    x1, y1, x2, y2 = box
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    half_width = max(2.0, (x2 - x1) * inner_scale / 2.0)
    half_height = max(2.0, (y2 - y1) * inner_scale / 2.0)
    inner_x1 = max(0, int(center_x - half_width))
    inner_y1 = max(0, int(center_y - half_height))
    inner_x2 = min(points_3d.shape[1], int(center_x + half_width) + 1)
    inner_y2 = min(points_3d.shape[0], int(center_y + half_height) + 1)

    roi_points = points_3d[inner_y1:inner_y2, inner_x1:inner_x2]
    roi_disparity = disparity[inner_y1:inner_y2, inner_x1:inner_x2]
    distances = (
        np.linalg.norm(roi_points, axis=2)
        if mode == "euclidean"
        else roi_points[:, :, 2]
    )
    valid = (
        np.isfinite(distances)
        & (roi_disparity > 0.5)
        & (distances >= min_distance_m)
        & (distances <= max_distance_m)
    )
    samples = distances[valid]
    if samples.size < 20:
        return None
    low, high = np.percentile(samples, (10, 90))
    trimmed = samples[(samples >= low) & (samples <= high)]
    return float(np.median(trimmed)) if trimmed.size >= 10 else None


def _disparity_preview(disparity: np.ndarray, num_disparities: int) -> np.ndarray:
    normalized = np.clip(disparity / float(num_disparities), 0.0, 1.0)
    preview = cv2.applyColorMap(
        (normalized * 255.0).astype(np.uint8), cv2.COLORMAP_TURBO
    )
    preview[disparity <= 0.5] = (20, 20, 20)
    return preview


class RobotStereoDetectionService:
    """Run one shared stereo/YOLO pipeline and retain two newest JPEG views."""

    def __init__(self) -> None:
        self.source_dir = Path(os.getenv("R1_STEREO_SOURCE_DIR", str(REFERENCE_DIR)))
        self.calibration_path = Path(
            os.getenv(
                "R1_STEREO_CALIBRATION",
                str(self.source_dir / "r1_stereo_calibration.npz"),
            )
        )
        self.model_path = Path(
            os.getenv(
                "R1_YOLO_WORLD_MODEL",
                str(BACKEND_DIR / "models" / "yolov8s-worldv2.pt"),
            )
        )
        self.prompts = [
            item.strip()
            for item in os.getenv("R1_YOLO_WORLD_CLASSES", DEFAULT_CLASSES).split(",")
            if item.strip()
        ]
        self.left_port = _env_int("R1_STEREO_LEFT_PORT", 5002)
        self.right_port = _env_int("R1_STEREO_RIGHT_PORT", 5003)
        self.width = _env_int("R1_STEREO_WIDTH", 544)
        self.height = _env_int("R1_STEREO_HEIGHT", 448)
        self.capture_backend = os.getenv("R1_STEREO_CAPTURE_BACKEND", "auto")
        self.confidence = min(_env_float("R1_YOLO_CONFIDENCE", 0.25), 1.0)
        self.image_size = _env_int("R1_YOLO_IMAGE_SIZE", 416)
        self.detect_every = _env_int("R1_YOLO_DETECT_EVERY", 2)
        self.device = os.getenv("R1_YOLO_DEVICE", "").strip() or None
        self.num_disparities = _env_int("R1_STEREO_NUM_DISPARITIES", 64, 16)
        self.num_disparities = max(16, (self.num_disparities // 16) * 16)
        self.block_size = _env_int("R1_STEREO_BLOCK_SIZE", 3, 3)
        if self.block_size % 2 == 0:
            self.block_size += 1
        self.inner_scale = min(_env_float("R1_STEREO_INNER_SCALE", 0.4), 1.0)
        self.min_distance_m = _env_float("R1_STEREO_MIN_DISTANCE_M", 0.15)
        self.max_distance_m = _env_float("R1_STEREO_MAX_DISTANCE_M", 15.0)
        self.max_pair_delta_ms = _env_float("R1_STEREO_MAX_PAIR_DELTA_MS", 80.0)
        self.distance_mode = os.getenv("R1_STEREO_DISTANCE_MODE", "z")
        if self.distance_mode not in {"z", "euclidean"}:
            self.distance_mode = "z"

        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._frames: dict[str, bytes | None] = {"detection": None, "depth": None}
        self._sequence = 0
        self._state = "stopped"
        self._error: str | None = None
        self._last_frame_at: float | None = None
        self._detections: list[dict[str, object]] = []
        self._fps = 0.0
        self._stereo_ms = 0.0
        self._yolo_ms = 0.0
        self._pair_delta_ms = 0.0
        self._baseline_m: float | None = None

    def _configuration_error(self) -> str | None:
        common_path = self.source_dir / "r1_stereo_common.py"
        if not common_path.is_file():
            return f"Stereo reference module not found: {common_path}"
        if not self.calibration_path.is_file():
            return f"Stereo calibration not found: {self.calibration_path}"
        if not self.model_path.is_file():
            return f"YOLO-World model not found: {self.model_path}"
        if not self.prompts:
            return "R1_YOLO_WORLD_CLASSES must contain at least one class."
        return None

    def start(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            error = self._configuration_error()
            if error:
                self._state = "error"
                self._error = error
                raise RobotStereoError(error)
            self._stop_event.clear()
            self._state = "loading"
            self._error = None
            self._thread = threading.Thread(
                target=self._run, name="r1-stereo-detection", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=30.0)
        with self._condition:
            if thread is not None and thread.is_alive():
                self._state = "stopping"
                self._error = "Stereo detection is still stopping; try again shortly."
            else:
                self._state = "stopped"
                self._error = None
            self._condition.notify_all()

    def set_classes(self, prompts: list[str]) -> dict[str, object]:
        normalized = []
        seen = set()
        for prompt in prompts:
            value = prompt.strip()
            key = value.casefold()
            if not value or key in seen:
                continue
            if len(value) > 80:
                raise RobotStereoError("Each object prompt must be 80 characters or less.")
            seen.add(key)
            normalized.append(value)
        if not normalized:
            raise RobotStereoError("Enter at least one object to detect.")
        if len(normalized) > 30:
            raise RobotStereoError("A maximum of 30 object prompts is supported.")

        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                raise RobotStereoStateError(
                    "Stop stereo detection before changing object prompts."
                )
            self.prompts = normalized
            self._detections = []
            self._error = None
        return self.status()

    def _load_common(self):
        path = self.source_dir / "r1_stereo_common.py"
        module_name = "r1_web_stereo_common"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise RobotStereoError(f"Could not load stereo helpers from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _set_terminal_error(self, message: str) -> None:
        with self._condition:
            self._state = "error"
            self._error = message
            self._condition.notify_all()

    def _run(self) -> None:
        capture = None
        try:
            try:
                from ultralytics import YOLOWorld
                from ultralytics.nn import text_model as ultralytics_text_model
            except ImportError as exc:
                raise RobotStereoError(
                    "Ultralytics is not installed in the Python environment running "
                    "the backend. Install it with: python3 -m pip install "
                    "'ultralytics>=8.3.0'"
                ) from exc

            common = self._load_common()
            geometry = common.StereoGeometry(self.calibration_path)
            matcher = common.create_sgbm(self.num_disparities, self.block_size)
            model = YOLOWorld(str(self.model_path))
            # Reuse the reference folder's cached CLIP encoder instead of
            # requiring a network download from the backend working directory.
            ultralytics_text_model.WEIGHTS_DIR = self.source_dir / "weights"
            model.set_classes(self.prompts)
            capture = common.StereoRtpCapture(
                self.left_port,
                self.right_port,
                width=self.width,
                height=self.height,
                backend=self.capture_backend,
            )
            capture.start()
            with self._condition:
                self._state = "waiting"
                self._baseline_m = round(float(geometry.baseline_m), 4)
        except Exception as exc:
            self._set_terminal_error(f"Could not start stereo detection: {exc}")
            if capture is not None:
                capture.stop()
            return

        previous_time = time.monotonic()
        frame_index = 0
        cached_detections: list[tuple[int, int, int, int, str, float]] = []
        last_yolo_ms = 0.0
        try:
            while not self._stop_event.is_set():
                try:
                    left, right, pair_delta_ms = capture.read_pair(
                        timeout_s=2.0,
                        max_delta_ms=self.max_pair_delta_ms,
                    )
                except TimeoutError as exc:
                    with self._condition:
                        self._state = "waiting"
                        self._error = str(exc)
                    continue

                processing_started = time.monotonic()
                left_rectified, right_rectified = geometry.rectify(left, right)
                disparity = common.compute_disparity(
                    matcher, left_rectified, right_rectified
                )
                points_3d = geometry.points_from_disparity(disparity)
                stereo_ms = (time.monotonic() - processing_started) * 1000.0
                annotated = left_rectified.copy()

                if frame_index % self.detect_every == 0:
                    options = {
                        "conf": self.confidence,
                        "imgsz": self.image_size,
                        "verbose": False,
                    }
                    if self.device is not None:
                        options["device"] = self.device
                    yolo_started = time.monotonic()
                    result = model.predict(left_rectified, **options)[0]
                    last_yolo_ms = (time.monotonic() - yolo_started) * 1000.0
                    cached_detections = []
                    for detection in result.boxes:
                        coords = detection.xyxy[0].detach().cpu().tolist()
                        x1, y1, x2, y2 = (int(value) for value in coords)
                        x1 = max(0, min(annotated.shape[1] - 1, x1))
                        y1 = max(0, min(annotated.shape[0] - 1, y1))
                        x2 = max(x1 + 1, min(annotated.shape[1], x2))
                        y2 = max(y1 + 1, min(annotated.shape[0], y2))
                        class_id = int(detection.cls[0].item())
                        cached_detections.append(
                            (
                                x1,
                                y1,
                                x2,
                                y2,
                                str(result.names[class_id]),
                                float(detection.conf[0].item()),
                            )
                        )

                detection_payload = []
                for detection_index, detection in enumerate(cached_detections):
                    x1, y1, x2, y2, name, confidence = detection
                    color = DETECTION_COLORS[detection_index % len(DETECTION_COLORS)]
                    blue, green, red = color
                    color_hex = f"#{red:02x}{green:02x}{blue:02x}"
                    distance = _object_distance(
                        points_3d,
                        disparity,
                        (x1, y1, x2, y2),
                        self.inner_scale,
                        self.min_distance_m,
                        self.max_distance_m,
                        self.distance_mode,
                    )
                    detection_payload.append(
                        {
                            "name": name,
                            "confidence": round(confidence, 4),
                            "distance_m": round(distance, 3) if distance is not None else None,
                            "color": color_hex,
                        }
                    )
                    distance_text = "no depth" if distance is None else f"{distance:.2f} m"
                    label = f"{name} {confidence:.2f} | {distance_text}"
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(
                        annotated,
                        label,
                        (x1, max(20, y1 - 7)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

                frame_index += 1
                now = time.monotonic()
                instant_fps = 1.0 / max(now - previous_time, 1e-6)
                fps = instant_fps if self._fps == 0.0 else 0.9 * self._fps + 0.1 * instant_fps
                previous_time = now
                depth_view = _disparity_preview(disparity, self.num_disparities)
                ok_detection, detection_jpeg = cv2.imencode(
                    ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 82]
                )
                ok_depth, depth_jpeg = cv2.imencode(
                    ".jpg", depth_view, [cv2.IMWRITE_JPEG_QUALITY, 82]
                )
                if not ok_detection or not ok_depth:
                    raise RobotStereoError("Could not encode stereo output frames.")

                with self._condition:
                    self._frames["detection"] = detection_jpeg.tobytes()
                    self._frames["depth"] = depth_jpeg.tobytes()
                    self._sequence += 1
                    self._last_frame_at = time.time()
                    self._detections = detection_payload
                    self._fps = fps
                    self._stereo_ms = stereo_ms
                    self._yolo_ms = last_yolo_ms
                    self._pair_delta_ms = pair_delta_ms
                    self._state = "connected"
                    self._error = None
                    self._condition.notify_all()
        except Exception as exc:
            if not self._stop_event.is_set():
                self._set_terminal_error(f"Stereo processing stopped: {exc}")
        finally:
            capture.stop()

    def status(self) -> dict[str, object]:
        with self._condition:
            age = (
                round(time.time() - self._last_frame_at, 3)
                if self._last_frame_at is not None
                else None
            )
            return {
                "configured": self._configuration_error() is None,
                "state": self._state,
                "running": self._thread is not None and self._thread.is_alive(),
                "connected": self._state == "connected",
                "error": self._error,
                "frame_sequence": self._sequence,
                "last_frame_age_seconds": age,
                "detections": list(self._detections),
                "fps": round(self._fps, 1),
                "stereo_ms": round(self._stereo_ms, 1),
                "yolo_ms": round(self._yolo_ms, 1),
                "pair_delta_ms": round(self._pair_delta_ms, 1),
                "baseline_m": self._baseline_m,
                "distance_mode": self.distance_mode,
                "classes": list(self.prompts),
                "ports": {"left": self.left_port, "right": self.right_port},
            }

    def mjpeg_stream(self, view: str) -> Iterator[bytes]:
        if view not in self._frames:
            raise RobotStereoError(f"Unknown stereo view: {view}")
        sequence = -1
        while not self._stop_event.is_set():
            with self._condition:
                self._condition.wait_for(
                    lambda: self._sequence > sequence
                    or self._stop_event.is_set()
                    or self._state == "error",
                    timeout=5.0,
                )
                if self._sequence <= sequence or self._frames[view] is None:
                    if self._state == "error":
                        break
                    continue
                jpeg = self._frames[view]
                sequence = self._sequence
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                + str(len(jpeg)).encode("ascii")
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
