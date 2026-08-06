from __future__ import annotations

from pathlib import Path

import requests

from common import MODELS_DIR, ensure_dirs


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


def download_file(url: str, output_path: Path) -> None:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    output_path.write_bytes(response.content)


def main() -> None:
    ensure_dirs()
    for filename, url in MODEL_URLS.items():
        output_path = MODELS_DIR / filename
        if output_path.exists():
            print(f"[OK] Da co model: {output_path.name}")
            continue
        print(f"[DOWNLOADING] {filename}")
        download_file(url, output_path)
        print(f"[SAVED] {output_path}")


if __name__ == "__main__":
    main()
