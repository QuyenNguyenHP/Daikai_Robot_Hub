"""English text-to-speech playback through the Unitree robot speaker."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path


SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2
STREAM_NAME = "facelens_speech"
MAX_TEXT_LENGTH = 200


class RobotSpeechError(RuntimeError):
    """Raised when text cannot be synthesized or played on the robot."""


class RobotSpeechBusyError(RobotSpeechError):
    """Raised when another speech request is already playing."""


class RobotSpeechService:
    def __init__(self, network_interface: str | None = None) -> None:
        self.network_interface = (
            network_interface or os.getenv("UNITREE_NETWORK_INTERFACE", "")
        ).strip()
        self._lock = threading.Lock()
        self._client = None
        self._tts = self._find_command("pico2wave", "espeak-ng", "espeak")
        self._converter = self._find_command("ffmpeg", "sox")

    @staticmethod
    def _find_command(*names: str) -> str | None:
        for name in names:
            executable = shutil.which(name)
            if executable:
                return executable
        return None

    def status(self) -> dict[str, object]:
        return {
            "configured": bool(self.network_interface),
            "available": bool(
                self.network_interface and self._tts and self._converter
            ),
            "busy": self._lock.locked(),
            "tts_backend": Path(self._tts).name if self._tts else None,
            "audio_converter": Path(self._converter).name if self._converter else None,
        }

    def _validate(self, text: str) -> str:
        normalized = " ".join(text.strip().split())
        if not normalized:
            raise RobotSpeechError("Speech text cannot be empty.")
        if len(normalized) > MAX_TEXT_LENGTH:
            raise RobotSpeechError(
                f"Speech text cannot exceed {MAX_TEXT_LENGTH} characters."
            )
        if not self.network_interface:
            raise RobotSpeechError("UNITREE_NETWORK_INTERFACE is not configured.")
        if not self._tts:
            raise RobotSpeechError("Install espeak-ng, espeak, or pico2wave.")
        if not self._converter:
            raise RobotSpeechError("Install ffmpeg or sox.")
        return normalized

    def _audio_client(self):
        if self._client is not None:
            return self._client
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
        except ImportError as exc:
            raise RobotSpeechError(f"Unitree SDK could not be imported: {exc}") from exc

        try:
            ChannelFactoryInitialize(0, self.network_interface)
            client = AudioClient()
            client.SetTimeout(10.0)
            client.Init()
        except Exception as exc:
            raise RobotSpeechError(
                f"Could not initialize the Unitree audio client: {exc}"
            ) from exc
        self._client = client
        return client

    def _synthesize(self, text: str, raw_path: Path) -> None:
        tool = Path(self._tts).name.lower()
        if tool in {"espeak-ng", "espeak"}:
            command = [self._tts, "-v", "en-us", "-w", str(raw_path), text]
        else:
            command = [self._tts, "-l", "en-US", "-w", str(raw_path), text]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise RobotSpeechError(
                result.stderr.strip() or f"TTS synthesis failed with {tool}."
            )

    def _normalize(self, raw_path: Path, output_path: Path) -> None:
        tool = Path(self._converter).name.lower()
        if tool == "ffmpeg":
            command = [
                self._converter,
                "-y",
                "-i",
                str(raw_path),
                "-ac",
                str(CHANNELS),
                "-ar",
                str(SAMPLE_RATE),
                "-sample_fmt",
                "s16",
                str(output_path),
            ]
        else:
            command = [
                self._converter,
                str(raw_path),
                "-r",
                str(SAMPLE_RATE),
                "-c",
                str(CHANNELS),
                "-b",
                str(SAMPLE_WIDTH * 8),
                str(output_path),
            ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            raise RobotSpeechError(
                result.stderr.strip() or f"Audio conversion failed with {tool}."
            )

    @staticmethod
    def _read_pcm(wav_path: Path) -> tuple[bytes, float]:
        with wave.open(str(wav_path), "rb") as wav_file:
            if (
                wav_file.getframerate() != SAMPLE_RATE
                or wav_file.getnchannels() != CHANNELS
                or wav_file.getsampwidth() != SAMPLE_WIDTH
                or wav_file.getcomptype() != "NONE"
            ):
                raise RobotSpeechError(
                    "Generated audio is not 16 kHz mono 16-bit PCM."
                )
            frames = wav_file.readframes(wav_file.getnframes())
            duration = wav_file.getnframes() / wav_file.getframerate()
        return frames, duration

    @staticmethod
    def _play(client, pcm: bytes, duration: float) -> None:
        stream_id = str(int(time.time() * 1000))
        try:
            for index, offset in enumerate(range(0, len(pcm), 96_000)):
                chunk = pcm[offset : offset + 96_000]
                code, _ = client.PlayStream(STREAM_NAME, stream_id, chunk)
                if code != 0:
                    raise RobotSpeechError(
                        f"Robot rejected audio chunk {index} with code {code}."
                    )
                time.sleep(1.0)
            time.sleep(duration + 0.5)
        finally:
            client.PlayStop(STREAM_NAME)

    def speak(self, text: str) -> dict[str, object]:
        normalized = self._validate(text)
        if not self._lock.acquire(blocking=False):
            raise RobotSpeechBusyError("The robot is already speaking.")
        try:
            with tempfile.TemporaryDirectory(prefix="facelens_tts_") as temp_dir:
                raw_path = Path(temp_dir) / "speech_raw.wav"
                pcm_path = Path(temp_dir) / "speech_16k.wav"
                self._synthesize(normalized, raw_path)
                self._normalize(raw_path, pcm_path)
                pcm, duration = self._read_pcm(pcm_path)
                self._play(self._audio_client(), pcm, duration)
            return {
                "spoken": True,
                "text": normalized,
                "duration_seconds": round(duration, 2),
            }
        except RobotSpeechError:
            raise
        except Exception as exc:
            raise RobotSpeechError(f"Speech processing failed: {exc}") from exc
        finally:
            self._lock.release()
