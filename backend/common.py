"""Shared paths, model factories, and face-database file helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
MODELS_DIR = BACKEND_DIR / "models"
DATA_DIR = PROJECT_DIR / "data"
FACES_DIR = DATA_DIR / "faces"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"
METADATA_PATH = DATA_DIR / "metadata.json"


def ensure_data_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)


def load_metadata() -> dict[str, Any]:
    if not METADATA_PATH.exists():
        return {"people": {}}
    with METADATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_metadata(payload: dict[str, Any]) -> None:
    with METADATA_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def load_embeddings() -> tuple[list[str], np.ndarray]:
    if not EMBEDDINGS_PATH.exists():
        return [], np.empty((0, 128), dtype=np.float32)
    payload = np.load(EMBEDDINGS_PATH, allow_pickle=True)
    return payload["names"].tolist(), payload["embeddings"].astype(np.float32)


def save_embeddings(names: list[str], embeddings: np.ndarray) -> None:
    np.savez_compressed(
        EMBEDDINGS_PATH,
        names=np.array(names, dtype=object),
        embeddings=embeddings.astype(np.float32),
    )


def cosine_similarity(first: np.ndarray, second: np.ndarray) -> float:
    denominator = np.linalg.norm(first) * np.linalg.norm(second)
    if denominator == 0.0:
        return 0.0
    return float(np.dot(first, second) / denominator)


def create_detector(input_size: tuple[int, int]) -> cv2.FaceDetectorYN:
    return cv2.FaceDetectorYN.create(
        model=str(MODELS_DIR / "face_detection_yunet_2023mar.onnx"),
        config="",
        input_size=input_size,
        score_threshold=0.9,
        nms_threshold=0.3,
        top_k=5000,
    )


def create_recognizer() -> cv2.FaceRecognizerSF:
    return cv2.FaceRecognizerSF.create(
        model=str(MODELS_DIR / "face_recognition_sface_2021dec.onnx"),
        config="",
    )


def draw_label(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    """Draw a readable label; used by the standalone reference script."""
    cv2.rectangle(frame, (x, y - 24), (x + max(140, len(text) * 10), y), color, -1)
    cv2.putText(
        frame,
        text,
        (x + 6, y - 7),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
