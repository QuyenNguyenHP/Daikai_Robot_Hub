from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone

import cv2
import numpy as np

from backend.common import (
    FACES_DIR,
    MODELS_DIR,
    cosine_similarity,
    create_detector,
    create_recognizer,
    ensure_data_dirs,
    load_embeddings,
    load_metadata,
    save_embeddings,
    save_metadata,
)


DETECTOR_MODEL = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
ALLOWED_NAME = re.compile(r"^[^/\\\x00]{1,80}$")


class FaceService:
    def __init__(self) -> None:
        ensure_data_dirs()
        missing = [
            path.name
            for path in (DETECTOR_MODEL, RECOGNIZER_MODEL)
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Missing ONNX models: "
                + ", ".join(missing)
                + ". Run: python3 -m backend.download_models"
            )

        self.detector = create_detector((640, 480))
        self.recognizer = create_recognizer()
        self.lock = threading.RLock()

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = " ".join(name.strip().split())
        if not normalized or normalized in {".", ".."} or not ALLOWED_NAME.fullmatch(normalized):
            raise ValueError(
                "Name must be 1-80 characters and cannot contain / or \\."
            )
        return normalized

    @staticmethod
    def decode_image(payload: bytes) -> np.ndarray:
        encoded = np.frombuffer(payload, dtype=np.uint8)
        frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("The uploaded file is not a readable image.")
        return frame

    def _detect_faces(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)
        if faces is None:
            return np.empty((0, 15), dtype=np.float32)
        return faces

    def _feature(self, frame: np.ndarray, face: np.ndarray) -> np.ndarray:
        aligned = self.recognizer.alignCrop(frame, face)
        return self.recognizer.feature(aligned).flatten().astype(np.float32)

    @staticmethod
    def _box(face: np.ndarray, width: int, height: int) -> dict[str, int]:
        x, y, w, h = (int(value) for value in face[:4])
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + w, width), min(y + h, height)
        return {
            "x": int(x1),
            "y": int(y1),
            "width": int(max(x2 - x1, 0)),
            "height": int(max(y2 - y1, 0)),
        }

    def recognize(self, payload: bytes, threshold: float) -> dict[str, object]:
        frame = self.decode_image(payload)
        return self.recognize_frame(frame, threshold)

    def recognize_frame(
        self, frame: np.ndarray, threshold: float
    ) -> dict[str, object]:
        """Recognize an already-decoded frame from an upload or live camera."""
        height, width = frame.shape[:2]

        with self.lock:
            faces = self._detect_faces(frame)
            names, embeddings = load_embeddings()
            detections: list[dict[str, object]] = []

            for face in faces:
                feature = self._feature(frame, face)
                label = "unknown"
                score = 0.0
                if embeddings.size > 0:
                    scores = [cosine_similarity(feature, known) for known in embeddings]
                    best_index = int(np.argmax(scores))
                    score = float(scores[best_index])
                    if score >= threshold:
                        label = names[best_index]

                detections.append(
                    {
                        "name": label,
                        "confidence": round(score, 4),
                        "box": self._box(face, width, height),
                    }
                )

        return {
            "image": {"width": width, "height": height},
            "threshold": threshold,
            "count": len(detections),
            "detections": detections,
        }

    def enroll(self, raw_name: str, images: list[tuple[str, bytes]]) -> dict[str, object]:
        name = self.normalize_name(raw_name)
        accepted: list[tuple[str, np.ndarray, np.ndarray]] = []
        rejected: list[dict[str, str]] = []

        with self.lock:
            for filename, payload in images:
                try:
                    frame = self.decode_image(payload)
                except ValueError as error:
                    rejected.append({"file": filename, "reason": str(error)})
                    continue

                faces = self._detect_faces(frame)
                if len(faces) == 0:
                    rejected.append({"file": filename, "reason": "No face detected."})
                    continue

                largest_face = max(faces, key=lambda row: row[2] * row[3])
                feature = self._feature(frame, largest_face)
                height, width = frame.shape[:2]
                box = self._box(largest_face, width, height)
                crop = frame[
                    box["y"] : box["y"] + box["height"],
                    box["x"] : box["x"] + box["width"],
                ].copy()
                accepted.append((filename, feature, crop))

            if not accepted:
                return {
                    "name": name,
                    "accepted": 0,
                    "rejected": rejected,
                    "updated": False,
                }

            features = [item[1] for item in accepted]
            new_embedding = np.mean(np.stack(features), axis=0).astype(np.float32)
            names, embeddings = load_embeddings()
            if name in names:
                embeddings[names.index(name)] = new_embedding
            else:
                names.append(name)
                embeddings = (
                    np.expand_dims(new_embedding, axis=0)
                    if embeddings.size == 0
                    else np.vstack([embeddings, new_embedding])
                )

            person_dir = FACES_DIR / name
            person_dir.mkdir(parents=True, exist_ok=True)
            batch_id = int(time.time() * 1000)
            for index, (_, _, crop) in enumerate(accepted, start=1):
                if crop.size:
                    cv2.imwrite(str(person_dir / f"web_{batch_id}_{index:02d}.jpg"), crop)

            save_embeddings(names, embeddings)
            metadata = load_metadata()
            metadata.setdefault("people", {})[name] = {
                "samples": len(accepted),
                "updated_at_epoch": int(time.time()),
            }
            save_metadata(metadata)

        return {
            "name": name,
            "accepted": len(accepted),
            "rejected": rejected,
            "updated": True,
        }

    def people(self) -> list[dict[str, object]]:
        with self.lock:
            names, _ = load_embeddings()
            metadata = load_metadata().get("people", {})
            people: list[dict[str, object]] = []
            for name in names:
                details = metadata.get(name, {})
                epoch = details.get("updated_at_epoch")
                updated_at = None
                if isinstance(epoch, (int, float)):
                    updated_at = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
                people.append(
                    {
                        "name": name,
                        "samples": int(details.get("samples", 0)),
                        "updated_at": updated_at,
                        "stored_photos": len(list((FACES_DIR / name).glob("*.jpg"))),
                    }
                )
            return people
