from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
MODELS_DIR = BACKEND_ROOT / "models"
DATA_DIR = PROJECT_ROOT / "data"
FACES_DIR = DATA_DIR / "faces"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npz"
METADATA_PATH = DATA_DIR / "metadata.json"


def ensure_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FACES_DIR.mkdir(parents=True, exist_ok=True)


def load_metadata() -> dict[str, Any]:
    if not METADATA_PATH.exists():
        return {"people": {}}

    with METADATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_metadata(payload: dict[str, Any]) -> None:
    with METADATA_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def save_embeddings(names: list[str], vectors: np.ndarray) -> None:
    np.savez_compressed(
        EMBEDDINGS_PATH,
        names=np.array(names, dtype=object),
        embeddings=vectors.astype(np.float32),
    )


def load_embeddings() -> tuple[list[str], np.ndarray]:
    if not EMBEDDINGS_PATH.exists():
        return [], np.empty((0, 128), dtype=np.float32)

    payload = np.load(EMBEDDINGS_PATH, allow_pickle=True)
    names = payload["names"].tolist()
    embeddings = payload["embeddings"].astype(np.float32)
    return names, embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def create_detector(model_path: str, input_size: tuple[int, int]) -> cv2.FaceDetectorYN:
    return cv2.FaceDetectorYN.create(
        model=model_path,
        config="",
        input_size=input_size,
        score_threshold=0.9,
        nms_threshold=0.3,
        top_k=5000,
    )


def create_recognizer(model_path: str) -> cv2.FaceRecognizerSF:
    return cv2.FaceRecognizerSF.create(model=model_path, config="")


def draw_label(
    frame: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
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
