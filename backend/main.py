from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.face_service import FaceService
from backend.robot_battery import RobotBatteryService
from backend.robot_camera import RobotCameraError, RobotCameraService
from backend.robot_control import (
    RobotControlBusyError,
    RobotControlError,
    RobotControlService,
    RobotControlStateError,
)
from backend.robot_audio import (
    MAX_TEXT_LENGTH,
    RobotAudioBusyError,
    RobotAudioError,
    RobotAudioService,
)
from backend.robot_services import (
    RobotServiceBusyError,
    RobotServiceError,
    RobotServiceManager,
    RobotServiceProtectedError,
)
from backend.robot_stereo_detection import (
    RobotStereoDetectionService,
    RobotStereoError,
    RobotStereoStateError,
)


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_ENROLL_IMAGES = 30
MAX_ENROLL_BYTES = 100 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.face_service = FaceService()
    app.state.robot_camera = RobotCameraService()
    app.state.robot_battery = RobotBatteryService()
    app.state.robot_control = RobotControlService()
    app.state.robot_audio = RobotAudioService()
    app.state.robot_services = RobotServiceManager()
    app.state.robot_stereo_detection = RobotStereoDetectionService()
    app.state.robot_battery.start()
    if app.state.robot_camera.network_interface:
        app.state.robot_camera.start()
    try:
        yield
    finally:
        app.state.robot_camera.stop()
        app.state.robot_battery.stop()
        app.state.robot_control.stop()
        app.state.robot_stereo_detection.stop()
        app.state.robot_audio.stop()


app = FastAPI(
    title="Face Recognition API",
    version="1.0.0",
    description="YuNet + SFace recognition API for the React web application.",
    lifespan=lifespan,
)

origins = [
    value.strip()
    for value in os.getenv(
        "FR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if value.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def service(request: Request) -> FaceService:
    return request.app.state.face_service


def robot_camera(request: Request) -> RobotCameraService:
    return request.app.state.robot_camera


def robot_audio(request: Request) -> RobotAudioService:
    return request.app.state.robot_audio


def robot_battery(request: Request) -> RobotBatteryService:
    return request.app.state.robot_battery


def robot_control(request: Request) -> RobotControlService:
    return request.app.state.robot_control


def robot_services(request: Request) -> RobotServiceManager:
    return request.app.state.robot_services


def robot_stereo_detection(request: Request) -> RobotStereoDetectionService:
    return request.app.state.robot_stereo_detection


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


class LedRequest(BaseModel):
    red: int = Field(ge=0, le=255)
    green: int = Field(ge=0, le=255)
    blue: int = Field(ge=0, le=255)
    keep_on: bool = False


class ControlRequest(BaseModel):
    action: Literal[
        "stance",
        "zero_torque",
        "enable",
        "disable",
        "forward",
        "backward",
        "left",
        "right",
        "turn_left",
        "turn_right",
        "stop",
        "neck_enable",
        "neck_disable",
        "upper_body_enable",
        "upper_body_disable",
        "neck_up",
        "neck_down",
        "neck_left",
        "neck_right",
        "neck_center",
        "arm_blow_kiss_both",
        "arm_blow_kiss_left",
        "arm_blow_kiss_right",
        "arm_both_hands_up",
        "arm_clap",
        "arm_high_five",
        "arm_hug",
        "arm_refuse",
        "arm_right_hand_up",
        "arm_ultraman_ray",
        "arm_wave_under_head",
        "arm_wave",
        "arm_handshake",
        "arm_box_left_win",
        "arm_box_right_win",
        "arm_box_both_win",
        "arm_extend_right_arm",
        "arm_right_hand_heart",
        "arm_hands_up_right",
        "arm_emphasize",
        "arm_forward_push",
        "arm_release",
    ]


class UpperBodyJointRequest(BaseModel):
    joint_index: int
    position: float


class ServiceSwitchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool


class StereoClassesRequest(BaseModel):
    classes: list[str] = Field(min_length=1, max_length=30)


async def read_image(upload: UploadFile) -> bytes:
    payload = await upload.read(MAX_IMAGE_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail=f"{upload.filename}: empty file")
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"{upload.filename}: image exceeds the 10 MB limit",
        )
    return payload


@app.get("/api/health")
def health(request: Request) -> dict[str, object]:
    people = service(request).people()
    return {
        "status": "ok",
        "models_loaded": True,
        "people_count": len(people),
        "robot_camera": robot_camera(request).status(),
        "robot_battery": robot_battery(request).status(),
        "robot_control": robot_control(request).status(),
        "robot_audio": robot_audio(request).status(),
        "robot_stereo_detection": robot_stereo_detection(request).status(),
    }


@app.get("/api/people")
def list_people(request: Request) -> dict[str, object]:
    people = service(request).people()
    return {"count": len(people), "people": people}


@app.post("/api/recognize")
async def recognize(
    request: Request,
    image: UploadFile = File(...),
    threshold: float = Form(0.45),
) -> dict[str, object]:
    if not 0.0 <= threshold <= 1.0:
        raise HTTPException(status_code=422, detail="threshold must be between 0 and 1")
    payload = await read_image(image)
    try:
        return service(request).recognize(payload, threshold)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/robot/status")
def robot_status(request: Request) -> dict[str, object]:
    return robot_camera(request).status()


@app.get("/api/robot/battery")
def robot_battery_status(request: Request) -> dict[str, object]:
    return robot_battery(request).status()


@app.websocket("/api/robot/battery/ws")
async def robot_battery_status_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    battery: RobotBatteryService = websocket.app.state.robot_battery
    try:
        while True:
            await websocket.send_json(battery.status())
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, RuntimeError):
        return


@app.get("/api/robot/control/status")
def robot_control_status(request: Request) -> dict[str, object]:
    return robot_control(request).status()


@app.get("/api/robot/services")
def list_robot_services(request: Request) -> dict[str, object]:
    try:
        return robot_services(request).list()
    except RobotServiceBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/robot/services/switch")
def switch_robot_service(
    request: Request,
    payload: ServiceSwitchRequest,
) -> dict[str, object]:
    try:
        return robot_services(request).switch(payload.name, payload.enabled)
    except (RobotServiceBusyError, RobotServiceProtectedError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/robot/mode")
def robot_mode(request: Request) -> dict[str, object]:
    try:
        return robot_control(request).mode()
    except RobotControlBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.websocket("/api/robot/mode/ws")
async def robot_mode_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    control: RobotControlService = websocket.app.state.robot_control
    try:
        while True:
            try:
                payload = control.mode()
                payload["error"] = None
            except RobotControlBusyError as error:
                payload = {"error": str(error), "control_busy": True}
            except RobotControlError as error:
                payload = {"error": str(error), "control_busy": False}
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, RuntimeError):
        return


@app.get("/api/robot/stereo/status")
def robot_stereo_status(request: Request) -> dict[str, object]:
    return robot_stereo_detection(request).status()


@app.websocket("/api/robot/stereo/ws")
async def robot_stereo_status_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    detector: RobotStereoDetectionService = websocket.app.state.robot_stereo_detection
    try:
        while True:
            await websocket.send_json(detector.status())
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, RuntimeError):
        # RuntimeError is raised when the ASGI server has already closed the
        # connection before the next status update is sent.
        return


@app.post("/api/robot/stereo/start")
def start_robot_stereo(request: Request) -> dict[str, object]:
    detector = robot_stereo_detection(request)
    try:
        detector.start()
    except RobotStereoError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return detector.status()


@app.post("/api/robot/stereo/stop")
def stop_robot_stereo(request: Request) -> dict[str, object]:
    detector = robot_stereo_detection(request)
    detector.stop()
    return detector.status()


@app.post("/api/robot/stereo/classes")
def set_robot_stereo_classes(
    request: Request,
    payload: StereoClassesRequest,
) -> dict[str, object]:
    try:
        return robot_stereo_detection(request).set_classes(payload.classes)
    except RobotStereoStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotStereoError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/robot/stereo/stream/{view}")
def robot_stereo_stream(
    request: Request,
    view: Literal["detection", "depth"],
) -> StreamingResponse:
    detector = robot_stereo_detection(request)
    return StreamingResponse(
        detector.mjpeg_stream(view),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/robot/control")
def control_robot(request: Request, payload: ControlRequest) -> dict[str, object]:
    try:
        return robot_control(request).execute(payload.action)
    except (RobotControlBusyError, RobotControlStateError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/robot/upper-body")
def control_robot_upper_body(
    request: Request,
    payload: UpperBodyJointRequest,
) -> dict[str, object]:
    try:
        return robot_control(request).set_upper_body_joint(
            payload.joint_index,
            payload.position,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (RobotControlBusyError, RobotControlStateError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/robot/connect")
def connect_robot(request: Request) -> dict[str, object]:
    camera = robot_camera(request)
    robot_battery(request).start()
    try:
        camera.start()
    except RobotCameraError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return camera.status()


@app.get("/api/robot/snapshot")
def robot_snapshot(request: Request) -> Response:
    try:
        jpeg, sequence = robot_camera(request).snapshot()
    except RobotCameraError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Sequence": str(sequence),
        },
    )


@app.get("/api/robot/stream")
def robot_stream(request: Request) -> StreamingResponse:
    camera = robot_camera(request)
    try:
        camera.start()
    except RobotCameraError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return StreamingResponse(
        camera.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/robot/recognize")
def recognize_robot_frame(
    request: Request,
    threshold: float = 0.45,
) -> dict[str, object]:
    if not 0.0 <= threshold <= 1.0:
        raise HTTPException(status_code=422, detail="threshold must be between 0 and 1")
    try:
        jpeg, sequence = robot_camera(request).snapshot()
        result = service(request).recognize(jpeg, threshold)
    except RobotCameraError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    result["frame_sequence"] = sequence
    return result


@app.get("/api/robot/speech/status")
def robot_speech_status(request: Request) -> dict[str, object]:
    return robot_audio(request).status()


@app.post("/api/robot/speak")
def speak_on_robot(request: Request, payload: SpeechRequest) -> dict[str, object]:
    try:
        return robot_audio(request).speak(payload.text)
    except RobotAudioBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotAudioError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/robot/led")
def set_robot_led(request: Request, payload: LedRequest) -> dict[str, object]:
    try:
        return robot_audio(request).set_led(
            payload.red,
            payload.green,
            payload.blue,
            payload.keep_on,
        )
    except RobotAudioBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotAudioError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/enroll")
async def enroll(
    request: Request,
    name: str = Form(...),
    images: list[UploadFile] = File(...),
) -> dict[str, object]:
    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")
    if len(images) > MAX_ENROLL_IMAGES:
        raise HTTPException(status_code=413, detail="Maximum 30 images per enrollment")

    try:
        normalized_name = FaceService.normalize_name(name)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    payloads: list[tuple[str, bytes]] = []
    total_bytes = 0
    for index, upload in enumerate(images, start=1):
        payload = await read_image(upload)
        total_bytes += len(payload)
        if total_bytes > MAX_ENROLL_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Enrollment upload exceeds the 100 MB total limit",
            )
        payloads.append((upload.filename or f"image_{index}.jpg", payload))

    result = service(request).enroll(normalized_name, payloads)
    if not result["updated"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "No valid face was found; the database was not changed.",
                "rejected": result["rejected"],
            },
        )
    return result
