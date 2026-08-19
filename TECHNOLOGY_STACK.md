# Technology Stack

This document lists the languages, frameworks, libraries, tools, protocols, and deployment components currently used by the Facial Recognition project.

## 1. Frontend

- **React.js** — builds the user interface with reusable components and React Hooks.
- **React DOM** — renders the React application in the browser.
- **JavaScript (ES Modules)** — the main frontend programming language.
- **JSX** — defines component markup inside JavaScript files.
- **HTML5** — provides the application entry page and document structure.
- **CSS3** — provides layout, styling, responsive behavior, and visual effects.
- **Vite** — provides the development server and production build process.
- **Node.js 20 or newer** — runs Vite and the frontend build tools. Node.js is not used as the application backend.
- **npm 10 or newer** — installs and manages frontend packages.

### Browser APIs

- **Fetch API** — sends HTTP requests to the FastAPI backend.
- **FormData** — uploads enrollment and recognition images as multipart form data.
- **MediaDevices / `getUserMedia()`** — accesses a webcam connected to the browser device.
- **Canvas API** — captures webcam frames and converts them to JPEG blobs.
- **Blob, File, and URL APIs** — handle captured images and API responses.
- **Timers** — periodically refresh robot status, battery data, and recognition results.

The direct frontend packages are declared in [`frontend/package.json`](frontend/package.json).

## 2. Backend

- **Python 3.10** — the backend and robot-integration programming language.
- **FastAPI** — defines the REST API and application lifecycle.
- **Uvicorn** — runs the FastAPI application as an ASGI server.
- **Pydantic** — validates structured API request bodies.
- **FastAPI CORS middleware** — allows approved frontend origins to access the API.
- **python-multipart** — parses file uploads and multipart form submissions.
- **Requests** — downloads the required face-recognition models.
- **Python threading** — runs robot camera, battery, speech, and control operations safely in the background.

The direct Python packages are declared in [`requirements.txt`](requirements.txt). The API routes are defined in [`backend/main.py`](backend/main.py).

## 3. Face Detection and Recognition

- **OpenCV Contrib Python** — supplies image processing and the YuNet/SFace APIs.
- **OpenCV YuNet** — detects faces in uploaded or camera images.
- **OpenCV SFace** — aligns faces and generates recognition embeddings.
- **ONNX** — stores the pretrained YuNet and SFace models.
- **NumPy** — processes images and embeddings and calculates similarity scores.
- **Cosine similarity** — compares a detected face embedding with enrolled embeddings.
- **NPZ** — stores compressed face embeddings in `data/embeddings.npz`.
- **JSON** — stores enrollment metadata in `data/metadata.json`.
- **JPEG** — stores enrolled face crops and transports camera snapshots and frames.

The main recognition implementation is in [`backend/face_service.py`](backend/face_service.py), with shared model and data utilities in [`backend/common.py`](backend/common.py).

## 4. Unitree R1 Robot Integration

- **Unitree SDK2 Python (`unitree_sdk2py`)** — communicates with the Unitree R1 robot.
- **Cyclone DDS / DDS** — provides the underlying real-time communication layer.
- **Unitree `VideoClient`** — receives images from the robot camera.
- **Unitree `LocoClient`** — sends movement commands and queries the locomotion FSM mode.
- **Unitree `AudioClient`** — streams PCM audio to the robot speaker.
- **Unitree DDS BMS messages** — provide live battery telemetry.

The robot services use environment variables including:

- `UNITREE_NETWORK_INTERFACE` — selects the network interface connected to the robot.
- `UNITREE_BATTERY_TOPIC` — optionally overrides the default DDS battery topic.

The integration is implemented in:

- [`backend/robot_camera.py`](backend/robot_camera.py)
- [`backend/robot_control.py`](backend/robot_control.py)
- [`backend/robot_battery.py`](backend/robot_battery.py)
- [`backend/robot_audio.py`](backend/robot_audio.py)

The Unitree SDK is an optional external dependency and is loaded only when robot functionality is used. It is not listed in the project's main `requirements.txt` because it has a separate installation process.

## 5. Speech and Audio Tools

Robot speech requires one text-to-speech engine:

- **pico2wave** (preferred), or
- **espeak-ng**, or
- **espeak**.

It also requires one audio conversion tool:

- **FFmpeg**, or
- **SoX**.

The selected tools generate and normalize speech as 16 kHz, mono, 16-bit PCM WAV audio before it is streamed through the Unitree `AudioClient`.

## 6. Frontend–Backend Communication

- **HTTP REST API** — handles health checks, face enrollment, recognition, and robot operations.
- **JSON** — transfers structured requests and responses.
- **`multipart/form-data`** — uploads one or more images.
- **JPEG snapshots** — return individual robot-camera frames.
- **MJPEG (`multipart/x-mixed-replace`)** — streams live robot-camera frames.
- **CORS** — supports frontend and backend development on different origins.

The project does not currently use WebSockets.

## 7. Deployment and Operating Environment

- **Apache2** — serves the production frontend build.
- **Apache `proxy` and `proxy_http` modules** — reverse-proxy `/api/*` requests to FastAPI/Uvicorn.
- **Apache `rewrite` module** — supports frontend client-side paths.
- **Apache `headers` module** — manages required HTTP headers.
- **systemd** — runs the backend automatically as a Linux service.
- **Raspberry Pi OS, Debian, or Ubuntu Linux** — documented deployment environments.
- **Python `venv` and pip** — isolate and install Python packages.

Deployment instructions are available in [`APACHE2_LAN_SETUP_vi.md`](APACHE2_LAN_SETUP_vi.md).

## 8. Source and Data Formats

| Format | Purpose |
| --- | --- |
| `.py` | Backend and robot scripts |
| `.js` | Frontend services, hooks, and Vite configuration |
| `.jsx` | React components and pages |
| `.css` | Application styling |
| `.html` | Frontend entry document |
| `.json` | npm metadata and application metadata |
| `.npz` | Compressed NumPy face embeddings |
| `.onnx` | Pretrained face detection and recognition models |
| `.jpg` / `.png` | Face samples and frontend image assets |
| `.md` | Project documentation |

## 9. Stack Summary

```text
Frontend:   React + JavaScript/JSX + HTML + CSS + Vite
Build:      Node.js + npm
Backend:    Python + FastAPI + Uvicorn + Pydantic
Vision/AI:  OpenCV YuNet + OpenCV SFace + ONNX + NumPy
Robot:      Unitree SDK2 Python + Cyclone DDS
Audio:      pico2wave/espeak + FFmpeg/SoX
Deployment: Apache2 + systemd + Raspberry Pi/Linux
```

## 10. Technologies Not Currently Used

Based on the current source code and dependency manifests, the project does not use:

- Node.js or Express as the backend
- TypeScript
- Next.js
- React Router
- Redux or another global state-management library
- SQL or NoSQL databases
- WebSockets
- Docker or Docker Compose
- A cloud hosting SDK
