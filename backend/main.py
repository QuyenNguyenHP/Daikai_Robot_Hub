from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
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
from backend.robot_speech import (
    MAX_TEXT_LENGTH,
    RobotSpeechBusyError,
    RobotSpeechError,
    RobotSpeechService,
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
    app.state.robot_speech = RobotSpeechService()
    app.state.robot_battery.start()
    if app.state.robot_camera.network_interface:
        app.state.robot_camera.start()
    try:
        yield
    finally:
        app.state.robot_camera.stop()
        app.state.robot_battery.stop()
        app.state.robot_control.stop()


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


def robot_speech(request: Request) -> RobotSpeechService:
    return request.app.state.robot_speech


def robot_battery(request: Request) -> RobotBatteryService:
    return request.app.state.robot_battery


def robot_control(request: Request) -> RobotControlService:
    return request.app.state.robot_control


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


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
        "robot_speech": robot_speech(request).status(),
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


@app.get("/api/robot/control/status")
def robot_control_status(request: Request) -> dict[str, object]:
    return robot_control(request).status()


@app.get("/api/robot/mode")
def robot_mode(request: Request) -> dict[str, object]:
    try:
        return robot_control(request).mode()
    except RobotControlBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotControlError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/robot/control")
def control_robot(request: Request, payload: ControlRequest) -> dict[str, object]:
    try:
        return robot_control(request).execute(payload.action)
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
        headers={"Cache-Control": "no-store"},
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
    return robot_speech(request).status()


@app.post("/api/robot/speak")
def speak_on_robot(request: Request, payload: SpeechRequest) -> dict[str, object]:
    try:
        return robot_speech(request).speak(payload.text)
    except RobotSpeechBusyError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RobotSpeechError as error:
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
