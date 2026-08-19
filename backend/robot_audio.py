"""Unitree R1 audio client for speech playback and RGB LED control."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

from backend.unitree_dds import UNITREE_DDS_INIT_LOCK


SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2
STREAM_NAME = "facelens_speech"
MAX_TEXT_LENGTH = 200


class RobotAudioError(RuntimeError):
    """Raised when robot audio or LED control fails."""


class RobotAudioBusyError(RobotAudioError):
    """Raised when another audio-client request is already running."""


class RobotAudioService:
    def __init__(self, network_interface: str | None = None) -> None:
        self.network_interface = (
            network_interface or os.getenv("UNITREE_NETWORK_INTERFACE", "")
        ).strip()
        self._lock = threading.Lock()
        self._client = None
        self._tts = self._find_command("pico2wave", "espeak-ng", "espeak")
        self._converter = self._find_command("ffmpeg", "sox")
        self._led_rgb: tuple[int, int, int] | None = None
        self._led_state_lock = threading.Lock()
        self._led_keep_on = False
        self._led_stop_event = threading.Event()
        self._led_thread: threading.Thread | None = None
        try:
            interval = float(os.getenv("ROBOT_LED_KEEPALIVE_SECONDS", "0.5"))
        except ValueError:
            interval = 0.5
        self._led_keepalive_seconds = min(max(interval, 0.2), 10.0)

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
            "led_rgb": list(self._led_rgb) if self._led_rgb is not None else None,
            "led_keep_on": self._led_keep_on,
            "led_keepalive_seconds": self._led_keepalive_seconds,
        }

    def _validate(self, text: str) -> str:
        normalized = " ".join(text.strip().split())
        if not normalized:
            raise RobotAudioError("Speech text cannot be empty.")
        if len(normalized) > MAX_TEXT_LENGTH:
            raise RobotAudioError(
                f"Speech text cannot exceed {MAX_TEXT_LENGTH} characters."
            )
        if not self.network_interface:
            raise RobotAudioError("UNITREE_NETWORK_INTERFACE is not configured.")
        if not self._tts:
            raise RobotAudioError("Install espeak-ng, espeak, or pico2wave.")
        if not self._converter:
            raise RobotAudioError("Install ffmpeg or sox.")
        return normalized

    def _audio_client(self):
        if self._client is not None:
            return self._client
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient
        except ImportError as exc:
            raise RobotAudioError(f"Unitree SDK could not be imported: {exc}") from exc

        try:
            with UNITREE_DDS_INIT_LOCK:
                ChannelFactoryInitialize(0, self.network_interface)
                client = AudioClient()
                client.SetTimeout(10.0)
                client.Init()
        except Exception as exc:
            raise RobotAudioError(
                f"Could not initialize the Unitree audio client: {exc}"
            ) from exc
        self._client = client
        return client

    def _ensure_led_thread(self) -> None:
        if self._led_thread is not None and self._led_thread.is_alive():
            return
        self._led_stop_event.clear()
        self._led_thread = threading.Thread(
            target=self._led_keepalive_loop,
            name="unitree-led-keepalive",
            daemon=True,
        )
        self._led_thread.start()

    def _led_keepalive_loop(self) -> None:
        while not self._led_stop_event.wait(self._led_keepalive_seconds):
            with self._led_state_lock:
                keep_on = self._led_keep_on
                rgb = self._led_rgb
            if not keep_on or rgb is None or not self._lock.acquire(blocking=False):
                continue
            try:
                self._audio_client().LedControl(*rgb)
            except Exception:
                # Retry temporary RPC failures at the next interval.
                pass
            finally:
                self._lock.release()

    def stop(self) -> None:
        self._led_stop_event.set()
        thread = self._led_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def set_led(
        self,
        red: int,
        green: int,
        blue: int,
        keep_on: bool = False,
    ) -> dict[str, object]:
        rgb = (red, green, blue)
        if any(isinstance(value, bool) or not 0 <= value <= 255 for value in rgb):
            raise RobotAudioError("LED RGB values must be integers from 0 to 255.")
        if not self.network_interface:
            raise RobotAudioError("UNITREE_NETWORK_INTERFACE is not configured.")
        if not self._lock.acquire(blocking=False):
            raise RobotAudioBusyError(
                "The robot audio service is busy; wait for speech to finish."
            )
        try:
            code = self._audio_client().LedControl(red, green, blue)
            if code != 0:
                raise RobotAudioError(f"LedControl failed with code {code}.")
            with self._led_state_lock:
                self._led_rgb = rgb
                self._led_keep_on = keep_on
            if keep_on:
                self._ensure_led_thread()
            return {
                "updated": True,
                "red": red,
                "green": green,
                "blue": blue,
                "keep_on": keep_on,
            }
        except RobotAudioError:
            raise
        except Exception as exc:
            raise RobotAudioError(f"Could not set the robot LED: {exc}") from exc
        finally:
            self._lock.release()

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
            raise RobotAudioError(
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
            raise RobotAudioError(
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
                raise RobotAudioError(
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
                    raise RobotAudioError(
                        f"Robot rejected audio chunk {index} with code {code}."
                    )
                time.sleep(1.0)
            time.sleep(duration + 0.5)
        finally:
            client.PlayStop(STREAM_NAME)

    def speak(self, text: str) -> dict[str, object]:
        normalized = self._validate(text)
        if not self._lock.acquire(blocking=False):
            raise RobotAudioBusyError("The robot is already speaking.")
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
        except RobotAudioError:
            raise
        except Exception as exc:
            raise RobotAudioError(f"Speech processing failed: {exc}") from exc
        finally:
            self._lock.release()
