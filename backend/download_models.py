"""Download the YuNet and SFace ONNX models when they are missing."""

from pathlib import Path

import requests

from backend.common import MODELS_DIR, ensure_data_dirs


MODEL_URLS = {
    "face_detection_yunet_2023mar.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
        "face_detection_yunet_2023mar.onnx"
    ),
    "face_recognition_sface_2021dec.onnx": (
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/"
        "face_recognition_sface_2021dec.onnx"
    ),
}


def download(url: str, destination: Path) -> None:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    destination.write_bytes(response.content)


def main() -> None:
    ensure_data_dirs()
    for filename, url in MODEL_URLS.items():
        destination = MODELS_DIR / filename
        if destination.exists():
            print(f"Already present: {destination}")
            continue
        print(f"Downloading: {filename}")
        download(url, destination)
        print(f"Saved: {destination}")


if __name__ == "__main__":
    main()
