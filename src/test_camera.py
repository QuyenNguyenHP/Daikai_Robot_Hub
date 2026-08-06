from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

from common import DATA_DIR, ensure_dirs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test webcam va cau hinh camera cho Raspberry Pi 5."
    )
    parser.add_argument("--camera-id", type=int, default=0, help="ID cua webcam.")
    parser.add_argument("--width", type=int, default=640, help="Do rong mong muon.")
    parser.add_argument("--height", type=int, default=480, help="Do cao mong muon.")
    parser.add_argument("--fps", type=int, default=20, help="FPS mong muon.")
    parser.add_argument(
        "--backend-v4l2",
        action="store_true",
        help="Thu mo camera bang backend V4L2.",
    )
    return parser.parse_args()


def open_camera(camera_id: int, use_v4l2: bool) -> cv2.VideoCapture:
    if use_v4l2:
        return cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
    return cv2.VideoCapture(camera_id)


def print_camera_info(capture: cv2.VideoCapture, requested: argparse.Namespace) -> None:
    actual_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = float(capture.get(cv2.CAP_PROP_FPS))
    print("=== Camera Info ===")
    print(f"Camera ID        : {requested.camera_id}")
    print(f"Requested size   : {requested.width}x{requested.height}")
    print(f"Actual size      : {actual_width}x{actual_height}")
    print(f"Requested FPS    : {requested.fps}")
    print(f"Actual FPS       : {actual_fps:.2f}")
    print("Phim tat         : q de thoat, s de chup anh")
    print("===================")


def main() -> None:
    args = parse_args()
    ensure_dirs()

    output_dir = DATA_DIR / "camera_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    capture = open_camera(args.camera_id, args.backend_v4l2)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    capture.set(cv2.CAP_PROP_FPS, args.fps)

    if not capture.isOpened():
        raise RuntimeError(
            "Khong mo duoc camera. Thu doi --camera-id hoac them --backend-v4l2."
        )

    print_camera_info(capture, args)

    last_time = time.time()
    fps_counter = 0
    display_fps = 0.0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Khong doc duoc frame tu camera.")
                break

            fps_counter += 1
            now = time.time()
            elapsed = now - last_time
            if elapsed >= 1.0:
                display_fps = fps_counter / elapsed
                fps_counter = 0
                last_time = now

            preview = frame.copy()
            cv2.putText(
                preview,
                f"Camera ID: {args.camera_id}",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                f"Frame: {preview.shape[1]}x{preview.shape[0]}",
                (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                f"Live FPS: {display_fps:.1f}",
                (10, 85),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                preview,
                "Nhan q de thoat | s de chup anh",
                (10, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("Camera Test", preview)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            if key == ord("s"):
                filename = f"camera_test_{int(time.time())}.jpg"
                output_path = output_dir / filename
                cv2.imwrite(str(output_path), frame)
                print(f"Da luu anh test: {output_path}")
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
