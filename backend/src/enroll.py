from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from common import (
    FACES_DIR,
    MODELS_DIR,
    create_detector,
    create_recognizer,
    draw_label,
    ensure_dirs,
    load_embeddings,
    load_metadata,
    save_embeddings,
    save_metadata,
)


DETECTOR_MODEL = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODELS_DIR / "face_recognition_sface_2021dec.onnx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dang ky khuon mat moi tu webcam hoac thu muc anh."
    )
    parser.add_argument("--name", required=True, help="Ten nguoi can dang ky.")
    parser.add_argument(
        "--image-dir",
        type=Path,
        help="Thu muc anh co san. Neu bo qua, chuong trinh se dung webcam.",
    )
    parser.add_argument("--camera-id", type=int, default=0, help="ID webcam.")
    parser.add_argument(
        "--samples",
        type=int,
        default=15,
        help="So luong mau khuon mat can thu thap.",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=0.7,
        help="Thoi gian cho giua hai lan chup hop le.",
    )
    return parser.parse_args()


def ensure_models_exist() -> None:
    missing = [path.name for path in (DETECTOR_MODEL, RECOGNIZER_MODEL) if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Chua co model ONNX. Hay chay: python3 backend/src/download_models.py\n"
            f"Model thieu: {', '.join(missing)}"
        )


def open_camera(camera_id: int) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(camera_id)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return capture


def detect_largest_face(
    detector: cv2.FaceDetectorYN,
    frame: np.ndarray,
) -> np.ndarray | None:
    height, width = frame.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(frame)
    if faces is None or len(faces) == 0:
        return None
    return max(faces, key=lambda row: row[2] * row[3])


def extract_feature(
    recognizer: cv2.FaceRecognizerSF,
    frame: np.ndarray,
    face: np.ndarray,
) -> np.ndarray:
    aligned = recognizer.alignCrop(frame, face)
    feature = recognizer.feature(aligned)
    return feature.flatten().astype(np.float32)


def update_database(person_name: str, features: list[np.ndarray]) -> None:
    names, embeddings = load_embeddings()
    metadata = load_metadata()

    new_embedding = np.mean(np.stack(features), axis=0).astype(np.float32)

    if person_name in names:
        idx = names.index(person_name)
        embeddings[idx] = new_embedding
    else:
        names.append(person_name)
        if embeddings.size == 0:
            embeddings = np.expand_dims(new_embedding, axis=0)
        else:
            embeddings = np.vstack([embeddings, new_embedding])

    save_embeddings(names, embeddings)
    metadata.setdefault("people", {})[person_name] = {
        "samples": len(features),
        "updated_at_epoch": int(time.time()),
    }
    save_metadata(metadata)


def enroll_from_images(
    image_dir: Path,
    person_dir: Path,
    sample_limit: int,
    detector: cv2.FaceDetectorYN,
    recognizer: cv2.FaceRecognizerSF,
) -> list[np.ndarray]:
    if not image_dir.is_dir():
        raise NotADirectoryError(f"Khong tim thay thu muc anh: {image_dir}")

    supported_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    image_paths = sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in supported_extensions
    )
    if not image_paths:
        raise FileNotFoundError(
            f"Khong co anh JPG, JPEG, PNG, BMP hoac WEBP trong: {image_dir}"
        )

    collected_features: list[np.ndarray] = []
    for image_path in image_paths:
        frame = cv2.imread(str(image_path))
        if frame is None:
            print(f"Bo qua anh khong doc duoc: {image_path.name}")
            continue

        face = detect_largest_face(detector, frame)
        if face is None:
            print(f"Bo qua anh khong tim thay khuon mat: {image_path.name}")
            continue

        collected_features.append(extract_feature(recognizer, frame, face))

        x, y, w, h = face[:4].astype(int)
        height, width = frame.shape[:2]
        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + w, width), min(y + h, height)
        face_img = frame[y1:y2, x1:x2]
        output_path = person_dir / f"sample_{len(collected_features):02d}.jpg"
        if face_img.size > 0:
            cv2.imwrite(str(output_path), face_img)

        print(
            f"Da xu ly mau {len(collected_features)}/{sample_limit}: "
            f"{image_path.name}"
        )
        if len(collected_features) >= sample_limit:
            break

    return collected_features


def main() -> None:
    args = parse_args()
    if args.samples < 1:
        raise ValueError("--samples phai lon hon hoac bang 1.")

    ensure_dirs()
    ensure_models_exist()

    person_dir = FACES_DIR / args.name
    person_dir.mkdir(parents=True, exist_ok=True)

    detector = create_detector(str(DETECTOR_MODEL), (640, 480))
    recognizer = create_recognizer(str(RECOGNIZER_MODEL))

    if args.image_dir is not None:
        collected_features = enroll_from_images(
            args.image_dir,
            person_dir,
            args.samples,
            detector,
            recognizer,
        )
        if not collected_features:
            raise RuntimeError(
                "Khong co anh nao chua khuon mat hop le; du lieu chua duoc cap nhat."
            )
        update_database(args.name, collected_features)
        print(
            f"Da dang ky xong cho {args.name} bang "
            f"{len(collected_features)} anh hop le."
        )
        return

    capture = open_camera(args.camera_id)

    if not capture.isOpened():
        raise RuntimeError("Khong mo duoc webcam. Kiem tra lai camera-id hoac ket noi USB.")

    collected_features: list[np.ndarray] = []
    last_capture_at = 0.0

    print("Nhan phim 's' de bat dau luu mau, 'q' de thoat.")

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Khong doc duoc frame tu webcam.")
                break

            frame = cv2.flip(frame, 1)
            face = detect_largest_face(detector, frame)

            if face is not None:
                x, y, w, h = face[:4].astype(int)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 0), 2)
                draw_label(
                    frame,
                    f"{args.name}: {len(collected_features)}/{args.samples}",
                    max(x, 0),
                    max(y, 28),
                    (0, 160, 0),
                )

            cv2.putText(
                frame,
                "Nhan s de luu mau, q de thoat",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("Enroll Face", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("s"):
                now = time.time()
                if face is None:
                    print("Khong tim thay khuon mat. Di chuyen lai truoc camera.")
                    continue
                if now - last_capture_at < args.cooldown:
                    print("Chup qua nhanh. Cho mot chut roi nhan s lai.")
                    continue

                feature = extract_feature(recognizer, frame, face)
                collected_features.append(feature)
                last_capture_at = now

                x, y, w, h = face[:4].astype(int)
                face_img = frame[max(y, 0): max(y, 0) + h, max(x, 0): max(x, 0) + w]
                image_path = person_dir / f"sample_{len(collected_features):02d}.jpg"
                cv2.imwrite(str(image_path), face_img)
                print(f"Da luu mau {len(collected_features)}/{args.samples}: {image_path.name}")

                if len(collected_features) >= args.samples:
                    update_database(args.name, collected_features)
                    print(f"Da dang ky xong cho {args.name}.")
                    break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
