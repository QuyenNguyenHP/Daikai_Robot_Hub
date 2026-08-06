from __future__ import annotations

import argparse
from collections import Counter, deque

import cv2
import numpy as np

from common import (
    EMBEDDINGS_PATH,
    MODELS_DIR,
    cosine_similarity,
    create_detector,
    create_recognizer,
    draw_label,
    ensure_dirs,
    load_embeddings,
)


DETECTOR_MODEL = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nhan dien khuon mat realtime bang webcam tren Raspberry Pi 5."
    )
    parser.add_argument("--camera-id", type=int, default=0, help="ID webcam.")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.45,
        help="Nguong cosine similarity de nhan la cung mot nguoi.",
    )
    parser.add_argument(
        "--history",
        type=int,
        default=5,
        help="So frame de bo phieu lam muot ket qua.",
    )
    return parser.parse_args()


def ensure_models_exist() -> None:
    missing = [path.name for path in (DETECTOR_MODEL, RECOGNIZER_MODEL) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Chua co model ONNX. Hay chay: python3 src/download_models.py\n"
            f"Model thieu: {', '.join(missing)}"
        )


def open_camera(camera_id: int) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(camera_id)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return capture


def detect_faces(
    detector: cv2.FaceDetectorYN,
    frame: np.ndarray,
) -> np.ndarray:
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
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    if best_score >= threshold:
        return names[best_idx], best_score
    return "unknown", best_score


def main() -> None:
    args = parse_args()
    ensure_dirs()
    ensure_models_exist()

    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(
            "Chua co du lieu dang ky. Hay chay enroll.py truoc de tao embeddings."
        )

    names, embeddings = load_embeddings()
    detector = create_detector(str(DETECTOR_MODEL), (640, 480))
    recognizer = create_recognizer(str(RECOGNIZER_MODEL))
    capture = open_camera(args.camera_id)
    if not capture.isOpened():
        raise RuntimeError("Khong mo duoc webcam. Kiem tra lai camera-id hoac ket noi USB.")

    history: deque[str] = deque(maxlen=max(args.history, 1))

    print("Nhan phim q de thoat.")

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Khong doc duoc frame tu webcam.")
                break

            frame = cv2.flip(frame, 1)
            faces = detect_faces(detector, frame)

            use_history = len(faces) == 1
            if not use_history:
                history.clear()

            for face in faces:
                label, score = match_face(
                    recognizer,
                    frame,
                    face,
                    names,
                    embeddings,
                    args.threshold,
                )
                stable_label = label
                if use_history:
                    history.append(label)
                    stable_label = Counter(history).most_common(1)[0][0]

                x, y, w, h = face[:4].astype(int)
                color = (0, 180, 0) if stable_label != "unknown" else (0, 0, 220)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                draw_label(
                    frame,
                    f"{stable_label} ({score:.2f})",
                    max(x, 0),
                    max(y, 28),
                    color,
                )

            cv2.putText(
                frame,
                "Nhan q de thoat",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("Realtime Face Recognition", frame)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
