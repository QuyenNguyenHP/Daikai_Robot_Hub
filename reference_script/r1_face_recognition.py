"""Realtime face recognition using the Unitree R1 camera stream.

This script uses the same YuNet/SFace models and ``data/embeddings.npz`` as
the rest of this project.  Enrol people with ``backend/src/enroll.py`` (or the
web UI) before running it.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter, deque
from pathlib import Path

import cv2
import numpy as np


# Running a file inside reference_script/ does not automatically put the
# project root on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.common import (  # noqa: E402
    EMBEDDINGS_PATH,
    MODELS_DIR,
    cosine_similarity,
    create_detector,
    create_recognizer,
    draw_label,
    load_embeddings,
)


DETECTOR_MODEL = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recognize enrolled faces using the Unitree R1 camera."
    )
    parser.add_argument(
        "network_interface",
        help="Network interface connected to the robot (for example eth0).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.45,
        help="Minimum cosine similarity for a known face (default: 0.45).",
    )
    parser.add_argument(
        "--history",
        type=int,
        default=5,
        help="Number of frames used to stabilize a single-face result (default: 5).",
    )
    parser.add_argument(
        "--process-every",
        type=int,
        default=1,
        help="Run recognition every N frames to reduce CPU usage (default: 1).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Do not open a video window; print recognition changes only.",
    )
    args = parser.parse_args()

    if not 0.0 <= args.threshold <= 1.0:
        parser.error("--threshold must be between 0 and 1")
    if args.history < 1:
        parser.error("--history must be at least 1")
    if args.process_every < 1:
        parser.error("--process-every must be at least 1")
    return args


def ensure_required_files() -> None:
    missing = [
        str(path)
        for path in (DETECTOR_MODEL, RECOGNIZER_MODEL, EMBEDDINGS_PATH)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Required face-recognition files are missing:\n- "
            + "\n- ".join(missing)
            + "\nDownload models with: python3 backend/src/download_models.py\n"
            + "Then enrol a person with: python3 backend/src/enroll.py --name NAME"
        )


def create_robot_video_client(network_interface: str):
    """Initialize Unitree DDS and return its video client."""
    try:
        from unitree_sdk2py.core.channel import ChannelFactoryInitialize
        from unitree_sdk2py.go2.video.video_client import VideoClient
    except ImportError as exc:
        raise RuntimeError(
            "unitree_sdk2py is not installed in this Python environment. "
            "Install Unitree SDK2 Python before running the robot camera script."
        ) from exc

    ChannelFactoryInitialize(0, network_interface)
    client = VideoClient()
    client.SetTimeout(3.0)
    client.Init()
    return client


def decode_robot_frame(data: object) -> np.ndarray | None:
    """Decode the JPEG byte array returned by VideoClient.GetImageSample."""
    try:
        encoded = np.frombuffer(bytes(data), dtype=np.uint8)
    except (TypeError, ValueError):
        return None
    if encoded.size == 0:
        return None
    return cv2.imdecode(encoded, cv2.IMREAD_COLOR)


def detect_faces(detector: cv2.FaceDetectorYN, frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(frame)
    if faces is None:
        return np.empty((0, 15), dtype=np.float32)
    return faces


def match_face(
    recognizer: cv2.FaceRecognizerSF,
    frame: np.ndarray,
    face: np.ndarray,
    names: list[str],
    embeddings: np.ndarray,
    threshold: float,
) -> tuple[str, float]:
    aligned = recognizer.alignCrop(frame, face)
    feature = recognizer.feature(aligned).flatten().astype(np.float32)
    if embeddings.size == 0:
        return "unknown", 0.0

    scores = [cosine_similarity(feature, known) for known in embeddings]
    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])
    label = names[best_index] if best_score >= threshold else "unknown"
    return label, best_score


def draw_detection(
    frame: np.ndarray,
    face: np.ndarray,
    label: str,
    score: float,
) -> None:
    x, y, width, height = face[:4].astype(int)
    color = (0, 180, 0) if label != "unknown" else (0, 0, 220)
    cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
    draw_label(
        frame,
        f"{label} ({score:.2f})",
        max(x, 0),
        max(y, 28),
        color,
    )


def run(args: argparse.Namespace) -> None:
    ensure_required_files()
    names, embeddings = load_embeddings()
    if not names:
        raise RuntimeError("No enrolled people were found in data/embeddings.npz.")

    detector = create_detector(str(DETECTOR_MODEL), (640, 480))
    recognizer = create_recognizer(str(RECOGNIZER_MODEL))

    print(f"Loaded {len(names)} enrolled people: {', '.join(names)}")
    print(f"Connecting to the R1 on interface {args.network_interface}...")
    client = create_robot_video_client(args.network_interface)
    print("Robot camera connected. Press q or Esc in the video window to stop.")

    history: deque[str] = deque(maxlen=args.history)
    frame_number = 0
    consecutive_errors = 0
    last_detections: list[tuple[np.ndarray, str, float]] = []
    last_reported: tuple[str, ...] | None = None

    try:
        while True:
            try:
                code, data = client.GetImageSample()
            except Exception as exc:
                consecutive_errors += 1
                print(f"Robot camera request failed ({consecutive_errors}/10): {exc}")
                if consecutive_errors >= 10:
                    raise RuntimeError("Robot camera failed 10 times consecutively.") from exc
                time.sleep(0.2)
                continue

            if code != 0:
                consecutive_errors += 1
                print(f"Robot camera returned code {code} ({consecutive_errors}/10).")
                if consecutive_errors >= 10:
                    raise RuntimeError("Robot camera failed 10 times consecutively.")
                time.sleep(0.2)
                continue

            frame = decode_robot_frame(data)
            if frame is None:
                consecutive_errors += 1
                if consecutive_errors >= 10:
                    raise RuntimeError("Could not decode 10 consecutive camera frames.")
                continue

            consecutive_errors = 0
            frame_number += 1

            if frame_number % args.process_every == 0 or not last_detections:
                faces = detect_faces(detector, frame)
                use_history = len(faces) == 1
                if not use_history:
                    history.clear()

                current: list[tuple[np.ndarray, str, float]] = []
                for face in faces:
                    label, score = match_face(
                        recognizer,
                        frame,
                        face,
                        names,
                        embeddings,
                        args.threshold,
                    )
                    if use_history:
                        history.append(label)
                        label = Counter(history).most_common(1)[0][0]
                    current.append((face.copy(), label, score))
                last_detections = current

                visible_names = tuple(sorted(label for _, label, _ in current))
                if visible_names != last_reported:
                    print(
                        "Detected: " + ", ".join(visible_names)
                        if visible_names
                        else "Detected: nobody"
                    )
                    last_reported = visible_names

            if not args.headless:
                for face, label, score in last_detections:
                    draw_detection(frame, face, label, score)
                cv2.imshow("Unitree R1 Face Recognition", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
    finally:
        cv2.destroyAllWindows()


def main() -> None:
    args = parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        print("\nStopped.")
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
