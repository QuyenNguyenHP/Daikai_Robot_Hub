# FaceLens: Webcam and Unitree R1 Face Recognition

FaceLens is a local face-enrollment and recognition application built with
FastAPI, React, OpenCV YuNet, and OpenCV SFace. The web interface can use either:

- the webcam attached to the browser's device; or
- the camera stream from a Unitree R1 robot connected to the backend machine.

The selected camera can be changed from both the **Recognize** and **Enroll**
screens. Enrolled identities and embeddings are shared by both camera sources.

## Architecture

```text
Browser webcam -> JPEG upload -----------+
                                           +-> FastAPI -> YuNet -> SFace
Unitree R1 -> Unitree SDK -> FastAPI -----+
```

The browser webcam continues to use `navigator.mediaDevices.getUserMedia()`.
The robot camera is read by one shared backend `VideoClient`; browsers never
need direct access to Unitree DDS.

## Requirements

- Python 3.11+
- Node.js 20+
- npm 10+
- Unitree SDK2 Python on the backend machine (only required for robot mode)
- A network interface connected to the robot (only required for robot mode)

Install the standard dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Install Unitree SDK2 Python according to Unitree's instructions and confirm
that this import works in the same Python environment as FastAPI:

```bash
python3 -c "from unitree_sdk2py.go2.video.video_client import VideoClient"
```

## Models

The YuNet and SFace ONNX files are already stored under `backend/models/`. If
they are missing, download them with:

```bash
python3 -m backend.download_models
```

## Start the application

### Webcam only

No robot configuration is required:

```bash
python3 backend/app.py
```

In a second terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`, choose **Device webcam**, and start the camera.

### Unitree R1 camera

Find the network interface connected to the robot:

```bash
ip link
```

Set that interface before starting the backend:

```bash
export UNITREE_NETWORK_INTERFACE=eth0
python3 backend/app.py
```

Then start the frontend, open the application, and choose **Unitree R1
camera**. The same selector is available for live recognition and enrollment.

If the frontend runs on another machine, configure its backend URL before
starting Vite:

```bash
export VITE_API_URL=http://BACKEND_IP:8000
cd frontend
npm run dev
```

Do not run multiple Uvicorn workers in robot mode. Unitree DDS initialization
and the camera client are process-global resources.

## Enroll people

From the **Enroll** screen:

1. Enter the person's name.
2. Select **Device webcam** or **Unitree R1 camera**.
3. Start the selected camera.
4. Capture 10-20 clear samples with small changes in angle and expression.
5. Select **Create face profile**.

Existing image-file upload remains available and can be combined with captured
samples. Data is stored in `data/faces/`, `data/embeddings.npz`, and
`data/metadata.json`.

## Robot API

The backend exposes:

| Endpoint                                     | Purpose                                   |
| -------------------------------------------- | ----------------------------------------- |
| `GET /api/robot/status`                    | Camera configuration and connection state |
| `POST /api/robot/connect`                  | Start the shared Unitree camera client    |
| `GET /api/robot/snapshot`                  | Latest robot JPEG frame                   |
| `GET /api/robot/stream`                    | MJPEG live preview                        |
| `POST /api/robot/recognize?threshold=0.45` | Recognize the latest robot frame          |

The original upload endpoints remain unchanged, so webcam mode and external API
clients remain compatible.

## Troubleshooting

- **Robot camera is not configured:** set `UNITREE_NETWORK_INTERFACE` before
  starting the backend.
- **`unitree_sdk2py` is not installed:** install the SDK into the Python
  environment used to launch FastAPI.
- **Robot stream does not connect:** verify the interface name, robot network,
  and that the reference Unitree camera script works on the backend machine.
- **Webcam permission is denied:** use `localhost` or HTTPS and allow camera
  permission in the browser.
- **Recognition is too strict or too permissive:** adjust the match threshold in
  the Recognize screen; `0.45` is the default.

Vietnamese setup notes for the original Raspberry Pi webcam workflow remain in
[`README_vi.md`](README_vi.md).
