# Backend Guide

This folder contains the FastAPI backend for **Daikai Robot Hub**. It supports
two image sources while keeping one shared face-recognition pipeline:

```text
Browser webcam -> POST /api/recognize --+
                                        +-> FaceService -> YuNet -> SFace
Unitree R1 -> RobotCameraService -------+
```

The browser owns the normal webcam. The backend never opens `/dev/video*`.
The backend owns the Unitree connection because the browser cannot talk to
Unitree DDS directly.

## Folder structure

```text
backend/
|-- __init__.py
|-- __main__.py
|-- app.py
|-- main.py
|-- common.py
|-- face_service.py
|-- robot_camera.py
|-- robot_battery.py
|-- robot_control.py
|-- robot_speech.py
|-- download_models.py
|-- models/
|   |-- face_detection_yunet_2023mar.onnx
|   `-- face_recognition_sface_2021dec.onnx
`-- README.md
```

The older `backend/src` programs are no longer part of the running app. Webcam
enrollment, recognition, and robot integrations now live behind the FastAPI
service in this folder.

## Entry points

### `__main__.py`

Command-line launcher for robot mode. It accepts the Unitree network interface,
sets `UNITREE_NETWORK_INTERFACE`, then starts Uvicorn with one worker.

From the project root:

```bash
python3 backend eth0
```

By default it listens on `0.0.0.0:8000`. You can override host and port:

```bash
python3 backend eth0 --host 127.0.0.1 --port 8000
```

This is the better launcher when you want the backend itself to set the robot
interface.

### `app.py`

Small development launcher. It adds the project root to `sys.path` and starts:

```bash
python backend/app.py
```

It always uses:

- `host="0.0.0.0"`
- `port=8000`
- `reload=True`

That makes it convenient for local development, but less ideal for Apache
reverse-proxy deployment on the Pi.

### `main.py`

Defines the FastAPI app, startup and shutdown lifecycle, request limits, CORS,
and every API endpoint.

During startup it creates exactly one instance of:

- `FaceService`
- `RobotCameraService`
- `RobotBatteryService`
- `RobotControlService`
- `RobotSpeechService`

During shutdown it stops the camera, battery subscriber, and robot control
service cleanly.

## Service modules

### `face_service.py`

Contains the shared face-recognition logic:

- decodes uploaded JPEG, PNG, and WebP images;
- detects faces with YuNet;
- aligns faces and extracts SFace embeddings;
- compares embeddings with cosine similarity;
- enrolls or updates a person;
- saves accepted face crops;
- lists enrolled people from metadata.

Both browser uploads and Unitree camera frames use this same service.

### `robot_camera.py`

Owns the Unitree camera connection. `RobotCameraService`:

1. reads `UNITREE_NETWORK_INTERFACE`;
2. delays importing `unitree_sdk2py` until robot mode is actually used;
3. initializes the DDS channel once;
4. starts one shared `VideoClient`;
5. captures JPEG frames in a background thread;
6. keeps only the newest frame;
7. exposes status, snapshot, and MJPEG stream helpers;
8. retries temporary camera-read failures.

If `UNITREE_NETWORK_INTERFACE` is missing, the service reports
`not_configured`.

### `robot_battery.py`

Subscribes to the Unitree battery DDS topic and keeps the latest reading ready
for API responses. It exposes battery status without making each HTTP request
wait on DDS traffic.

The topic defaults to the built-in battery topic, and you can override it with:

```bash
export UNITREE_BATTERY_TOPIC=...
```

### `robot_control.py`

Provides bounded locomotion control and FSM mode queries for the Unitree R1.

It supports these actions:

- `enable`
- `disable`
- `forward`
- `backward`
- `left`
- `right`
- `turn_left`
- `turn_right`
- `stop`

Only one control action can run at a time. Busy or invalid robot state
conditions are returned as HTTP `409` errors by the API layer.

### `robot_speech.py`

Converts English text into audio and plays it through the Unitree speaker.

It prefers:

1. `pico2wave`
2. `espeak-ng`
3. `espeak`

It then uses `ffmpeg` or `sox` to normalize the output to 16 kHz mono 16-bit
PCM before streaming it to the robot.

Speech is limited to `200` characters per request, and only one speech request
can run at a time.

### `common.py`

Contains shared helpers for:

- project, model, and data paths;
- metadata JSON loading and saving;
- embedding NPZ loading and saving;
- cosine similarity;
- YuNet and SFace factory creation.

Application data lives outside the backend package:

```text
data/
|-- embeddings.npz
|-- metadata.json
`-- faces/<person>/*.jpg
```

### `download_models.py`

Optional setup script that downloads missing YuNet and SFace ONNX models from
the OpenCV model zoo:

```bash
python -m backend.download_models
```

It is not imported by the running backend.

## API endpoints

| Method | Endpoint                     | Purpose |
| ------ | ---------------------------- | ------- |
| `GET`  | `/api/health`                | Overall API, model, people, and robot summary |
| `GET`  | `/api/people`                | List enrolled identities |
| `POST` | `/api/recognize`             | Recognize one uploaded browser image |
| `POST` | `/api/enroll`                | Enroll one person from uploaded images |
| `GET`  | `/api/robot/status`          | Unitree camera configuration and capture state |
| `GET`  | `/api/robot/battery`         | Latest Unitree battery telemetry |
| `GET`  | `/api/robot/control/status`  | Current locomotion-control service status |
| `GET`  | `/api/robot/mode`            | Current Unitree FSM mode |
| `POST` | `/api/robot/control`         | Send one bounded locomotion command |
| `POST` | `/api/robot/connect`         | Start the shared Unitree camera client |
| `GET`  | `/api/robot/snapshot`        | Return the newest Unitree JPEG |
| `GET`  | `/api/robot/stream`          | Return a live MJPEG stream |
| `POST` | `/api/robot/recognize`       | Recognize the newest Unitree frame |
| `GET`  | `/api/robot/speech/status`   | Report speech tool and busy status |
| `POST` | `/api/robot/speak`           | Convert English text and play it |

Interactive API docs are available while the backend is running:

```text
http://127.0.0.1:8000/docs
```

## Request limits

These limits are enforced in `main.py`:

- single uploaded image: `10 MB`
- maximum enrollment images per request: `30`
- maximum total enrollment payload: `100 MB`
- recognition threshold must be between `0.0` and `1.0`
- speech text length must be between `1` and `200` characters

## Startup behavior

On startup:

- `FaceService` loads the face models and database;
- `RobotBatteryService.start()` is called immediately;
- `RobotCameraService.start()` is called automatically only if
  `UNITREE_NETWORK_INTERFACE` is already configured.

That means webcam-only mode works without Unitree installed, while robot mode
can auto-connect when the interface is set before launch.

## Recommended run modes

### Webcam-only development

```bash
python backend/app.py
```

This is the easiest way to develop locally with Vite and browser webcam input.

### Robot mode with interface passed on the command line

```bash
python3 backend eth0
```

Use this when you want the backend launcher to set
`UNITREE_NETWORK_INTERFACE` for you.

### Apache reverse-proxy deployment on Raspberry Pi

If Apache proxies `/api/` to the backend, prefer binding only to localhost:

```bash
python3 backend eth0 --host 127.0.0.1 --port 8000
```

Or, if you already exported the interface yourself:

```bash
export UNITREE_NETWORK_INTERFACE=eth0
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

This keeps port `8000` off the LAN and lets Apache be the only public entry
point.

## CORS

The default allowed origins are:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Override them with a comma-separated environment variable:

```bash
export FR_CORS_ORIGINS=http://192.168.1.20:5173,http://10.0.0.50:5173
```

If you deploy the frontend behind Apache on the same host and use the same
origin, extra CORS configuration is usually unnecessary.

## Robot speech dependencies

Robot speech needs:

- one TTS engine: `pico2wave`, `espeak-ng`, or `espeak`
- one audio conversion tool: `ffmpeg` or `sox`

Example on Debian or Ubuntu:

```bash
sudo apt update
sudo apt install -y libttspico-utils ffmpeg
```

Check support and send a manual speech test:

```bash
curl http://127.0.0.1:8000/api/robot/speech/status
curl -X POST http://127.0.0.1:8000/api/robot/speak \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from Daikai Robot Hub"}'
```

## Robot states

### Camera service states

`RobotCameraService.status()` can report:

| State | Meaning |
| ----- | ------- |
| `not_configured` | `UNITREE_NETWORK_INTERFACE` is missing |
| `stopped` | Configured but capture has not started |
| `connecting` | DDS and camera client are starting |
| `connected` | Fresh JPEG frames are arriving |
| `reconnecting` | A temporary camera read failed and retry is in progress |
| `error` | SDK import or initialization failed |

## Quick verification

```bash
python -m py_compile backend/*.py
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/people
curl http://127.0.0.1:8000/api/robot/status
curl http://127.0.0.1:8000/api/robot/speech/status
curl http://127.0.0.1:8000/api/robot/snapshot --output /tmp/robot.jpg
```

When troubleshooting imports, confirm the backend is using the intended Python
interpreter:

```bash
which python
python --version
python -c "import fastapi, cv2; from unitree_sdk2py.go2.video.video_client import VideoClient; print('OK')"
```
