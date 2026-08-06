# Backend Guide

This folder contains the complete FastAPI backend for FaceLens. It supports two
image sources without duplicating the face-recognition pipeline:

```text
Browser webcam -> POST /api/recognize --+
                                      +-> FaceService -> YuNet -> SFace
Unitree R1 -> RobotCameraService ------+
```

The browser owns the normal webcam. The backend never opens `/dev/video*`.
The backend owns the Unitree connection because a browser cannot communicate
with Unitree DDS directly.

## Folder structure

```text
backend/
├── __init__.py
├── app.py
├── main.py
├── face_service.py
├── robot_camera.py
├── common.py
├── download_models.py
├── models/
│   ├── face_detection_yunet_2023mar.onnx
│   └── face_recognition_sface_2021dec.onnx
└── README.md
```

The old `backend/src` folder was removed. Its webcam enrollment, recognition,
and camera-test programs duplicated features now provided by the React web
application and were not imported by the running backend.

## Every Python script

### `__init__.py`

Marks `backend` as a Python package. It contains no startup logic. Keeping it
makes imports such as `from backend.face_service import FaceService` explicit
and reliable.

### `app.py`

Small development launcher. It adds the project root to `sys.path` and starts
Uvicorn with reload enabled:

```bash
python backend/app.py
```

Use one worker in robot mode. Unitree's DDS factory and camera client are shared
process-level resources.

### `main.py`

Defines the FastAPI application and all HTTP endpoints. During application
startup it creates exactly one `FaceService` and one `RobotCameraService`. On
shutdown it stops the robot capture thread.

It also handles:

- CORS configuration;
- upload size limits;
- request validation;
- conversion of service errors into HTTP responses;
- JPEG snapshots and MJPEG streaming.

### `face_service.py`

Contains all face-related application logic:

- decode uploaded JPEG/PNG images;
- detect faces with YuNet;
- align faces and generate SFace embeddings;
- compare embeddings with cosine similarity;
- enroll or update a person;
- save cropped enrollment photos;
- list enrolled people.

Both webcam uploads and Unitree frames use this same service. OpenCV model
objects are protected by a re-entrant lock because requests may run
concurrently.

### `robot_camera.py`

Owns the Unitree camera connection. `RobotCameraService`:

1. reads `UNITREE_NETWORK_INTERFACE`;
2. imports `unitree_sdk2py` only when robot mode starts;
3. calls `ChannelFactoryInitialize(0, interface)` once;
4. creates one `VideoClient`;
5. receives JPEG frames in a background thread;
6. keeps only the newest frame;
7. exposes status, snapshot, and MJPEG-generator methods;
8. retries temporary `GetImageSample()` failures.

The delayed Unitree import is intentional: webcam-only mode can run without the
Unitree SDK installed.

### `common.py`

Contains small helpers shared by the backend services:

- absolute project, model, and data paths;
- metadata JSON loading and saving;
- embedding NPZ loading and saving;
- cosine similarity;
- YuNet and SFace factory functions.

Application data remains outside the backend package:

```text
data/
├── embeddings.npz
├── metadata.json
└── faces/<person>/*.jpg
```

### `download_models.py`

Optional setup utility. It downloads missing YuNet and SFace models from the
OpenCV model repository and leaves existing files unchanged:

```bash
python -m backend.download_models
```

It is not imported by the running application.

## API endpoints

| Method   | Endpoint                 | Purpose                                    |
| -------- | ------------------------ | ------------------------------------------ |
| `GET`  | `/api/health`          | API, model, people, and robot summary      |
| `GET`  | `/api/people`          | List enrolled identities                   |
| `POST` | `/api/recognize`       | Recognize an uploaded webcam/image frame   |
| `POST` | `/api/enroll`          | Enroll images from webcam, robot, or files |
| `GET`  | `/api/robot/status`    | Unitree configuration and capture state    |
| `POST` | `/api/robot/connect`   | Start the shared Unitree client            |
| `GET`  | `/api/robot/snapshot`  | Return the newest Unitree JPEG             |
| `GET`  | `/api/robot/stream`    | Return an MJPEG Unitree preview            |
| `POST` | `/api/robot/recognize` | Recognize the newest Unitree frame         |

Interactive API documentation is available while the backend runs:

```text
http://127.0.0.1:8000/docs
```

## Configuration

### Webcam-only mode

No camera environment variable is required:

```bash
python backend/app.py
```

The React frontend captures webcam frames and sends them to the upload API.

### Unitree mode

Use the Conda environment containing a working `unitree_sdk2py` and CycloneDDS:

```bash
conda activate unitree
cd /home/r1-edu/Documents/Facial-Reconigtion
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6
python backend/app.py
```

Check the connection:

```bash
curl -s http://127.0.0.1:8000/api/robot/status | python -m json.tool
```

A working camera reports `"connected": true` and an increasing
`frame_sequence`.

### CORS

The default allowed frontend origins are `http://localhost:5173` and
`http://127.0.0.1:5173`. Override them with a comma-separated list:

```bash
export FR_CORS_ORIGINS=http://192.168.1.20:5173
```

## Request limits

- One uploaded image: 10 MB maximum.
- Enrollment batch: 30 images maximum.
- Enrollment batch total: 100 MB maximum.
- Recognition threshold: `0.0` through `1.0`; frontend default `0.45`.

## Robot states

| State              | Meaning                                         |
| ------------------ | ----------------------------------------------- |
| `not_configured` | `UNITREE_NETWORK_INTERFACE` is missing        |
| `stopped`        | Configured but capture has not started          |
| `connecting`     | DDS and`VideoClient` are initializing         |
| `connected`      | Fresh JPEG frames are arriving                  |
| `reconnecting`   | A temporary camera read failed; retrying        |
| `error`          | SDK import or initialization failed permanently |

## Quick verification

```bash
python -m py_compile backend/*.py
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/robot/status
curl http://127.0.0.1:8000/api/robot/snapshot --output /tmp/robot.jpg
```

When troubleshooting imports, confirm that the backend uses the intended
interpreter:

```bash
which python
python -c "import fastapi, cv2; from unitree_sdk2py.go2.video.video_client import VideoClient; print('OK')"
```
