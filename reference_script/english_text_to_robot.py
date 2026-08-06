import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient


TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2


def read_wav(filename):
    try:
        with open(filename, "rb") as f:
            def read(fmt):
                return struct.unpack(fmt, f.read(struct.calcsize(fmt)))

            chunk_id, = read("<I")
            if chunk_id != 0x46464952:
                return [], -1, -1, False

            _chunk_size, = read("<I")
            format_tag, = read("<I")
            if format_tag != 0x45564157:
                return [], -1, -1, False

            subchunk1_id, = read("<I")
            subchunk1_size, = read("<I")
            if subchunk1_id == 0x4B4E554A:
                f.seek(subchunk1_size, 1)
                subchunk1_id, = read("<I")
                subchunk1_size, = read("<I")

            if subchunk1_id != 0x20746D66:
                return [], -1, -1, False

            audio_format, = read("<H")
            if audio_format != 1:
                return [], -1, -1, False

            num_channels, = read("<H")
            sample_rate, = read("<I")
            _byte_rate, = read("<I")
            _block_align, = read("<H")
            bits_per_sample, = read("<H")

            if bits_per_sample != 16:
                return [], -1, -1, False

            if subchunk1_size == 18:
                extra_size, = read("<H")
                if extra_size != 0:
                    return [], -1, -1, False

            while True:
                subchunk2_id, subchunk2_size = read("<II")
                if subchunk2_id == 0x61746164:
                    break
                f.seek(subchunk2_size, 1)

            raw_pcm = f.read(subchunk2_size)
            if len(raw_pcm) != subchunk2_size:
                return [], -1, -1, False

            return list(raw_pcm), sample_rate, num_channels, True
    except Exception:
        return [], -1, -1, False


def play_pcm_stream(client, pcm_list, stream_name="english_text_to_robot", chunk_size=96000, sleep_time=1.0):
    pcm_data = bytes(pcm_list)
    stream_id = str(int(time.time() * 1000))
    offset = 0
    chunk_index = 0

    while offset < len(pcm_data):
        chunk = pcm_data[offset:offset + chunk_size]
        ret_code, _ = client.PlayStream(stream_name, stream_id, chunk)
        if ret_code != 0:
            raise RuntimeError(f"Failed to send chunk {chunk_index}, return code: {ret_code}")

        offset += len(chunk)
        chunk_index += 1
        time.sleep(sleep_time)


def find_tts_backend():
    for backend in ["pico2wave", "espeak-ng", "espeak"]:
        if shutil.which(backend):
            return backend
    raise RuntimeError("Install one of these TTS tools first: espeak-ng, espeak, pico2wave.")


def synthesize_tts(text, output_path: Path, backend: str):
    if backend in {"espeak-ng", "espeak"}:
        command = [backend, "-v", "en-us", "-w", str(output_path), text]
    elif backend == "pico2wave":
        command = [backend, "-l", "en-US", "-w", str(output_path), text]
    else:
        raise RuntimeError(f"Unsupported backend: {backend}")

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"TTS synthesis failed with {backend}.")


def normalize_wav(input_path: Path, output_path: Path):
    converter = shutil.which("ffmpeg") or shutil.which("sox")
    if not converter:
        raise RuntimeError("Install ffmpeg or sox to normalize WAV to 16kHz mono PCM.")

    tool_name = Path(converter).name.lower()
    if "ffmpeg" in tool_name:
        command = [
            converter,
            "-y",
            "-i",
            str(input_path),
            "-ac",
            str(TARGET_CHANNELS),
            "-ar",
            str(TARGET_SAMPLE_RATE),
            "-sample_fmt",
            "s16",
            str(output_path),
        ]
    else:
        command = [
            converter,
            str(input_path),
            "-r",
            str(TARGET_SAMPLE_RATE),
            "-c",
            str(TARGET_CHANNELS),
            "-b",
            str(TARGET_SAMPLE_WIDTH * 8),
            str(output_path),
        ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Audio normalization failed.")


def get_wav_duration_seconds(wav_path: Path):
    with wave.open(str(wav_path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def play_on_robot(network_interface: str, wav_path: Path):
    ChannelFactoryInitialize(0, network_interface)

    audio_client = AudioClient()
    audio_client.SetTimeout(10.0)
    audio_client.Init()

    pcm_list, sample_rate, num_channels, is_ok = read_wav(str(wav_path))
    if not is_ok or sample_rate != TARGET_SAMPLE_RATE or num_channels != TARGET_CHANNELS:
        raise RuntimeError("Generated WAV is not compatible with the robot audio stream requirements.")

    play_pcm_stream(audio_client, pcm_list)
    time.sleep(get_wav_duration_seconds(wav_path) + 0.5)
    audio_client.PlayStop("english_text_to_robot")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Speak English text on a Unitree robot using Ubuntu TTS plus robot audio playback."
    )
    parser.add_argument("network_interface", help="Network interface used to reach the robot.")
    parser.add_argument("text", help="English text to speak on the robot.")
    return parser.parse_args()


def main():
    args = parse_args()
    backend = find_tts_backend()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_input = Path(temp_dir) / "tts_raw.wav"
        temp_output = Path(temp_dir) / "tts_16k.wav"
        synthesize_tts(args.text, temp_input, backend)
        normalize_wav(temp_input, temp_output)
        play_on_robot(args.network_interface, temp_output)

    print("[INFO] English speech sent to robot successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
