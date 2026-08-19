import argparse
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.g1.audio.g1_audio_client import AudioClient


PRESET_COLORS = {
    "off": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "orange": (255, 128, 0),
}

MENU_OPTIONS = [
    ("1", "off"),
    ("2", "white"),
    ("3", "red"),
    ("4", "green"),
    ("5", "blue"),
    ("6", "yellow"),
    ("7", "cyan"),
    ("8", "magenta"),
    ("9", "orange"),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Set the Unitree robot LED strip to a chosen RGB color."
    )
    parser.add_argument(
        "network_interface",
        help="Network interface used to reach the robot.",
    )
    parser.add_argument(
        "--color",
        choices=sorted(PRESET_COLORS.keys()),
        help="Preset color name. Ignored when --r/--g/--b are all provided.",
    )
    parser.add_argument("--r", type=int, help="Red channel, 0-255.")
    parser.add_argument("--g", type=int, help="Green channel, 0-255.")
    parser.add_argument("--b", type=int, help="Blue channel, 0-255.")
    parser.add_argument(
        "--hold",
        type=float,
        default=0.3,
        help="Seconds to keep the client alive after sending the LED command.",
    )
    return parser.parse_args()


def prompt_menu_color():
    print("Choose an LED color:")
    for key, color_name in MENU_OPTIONS:
        print(f"  {key}. {color_name}")

    choice_to_color = dict(MENU_OPTIONS)
    while True:
        choice = input("Enter 1-9: ").strip()
        color_name = choice_to_color.get(choice)
        if color_name is not None:
            return PRESET_COLORS[color_name]
        print("Invalid choice. Please enter a number from 1 to 9.")


def resolve_rgb(args):
    manual_values = [args.r, args.g, args.b]
    provided_count = sum(value is not None for value in manual_values)

    if provided_count not in (0, 3):
        raise ValueError("Provide either all of --r/--g/--b or none of them.")

    if provided_count == 3:
        rgb = (args.r, args.g, args.b)
    elif args.color is not None:
        rgb = PRESET_COLORS[args.color]
    else:
        rgb = prompt_menu_color()

    for value, channel in zip(rgb, ("R", "G", "B")):
        if not 0 <= value <= 255:
            raise ValueError(f"{channel} must be between 0 and 255.")

    return rgb


def main():
    args = parse_args()
    red, green, blue = resolve_rgb(args)

    ChannelFactoryInitialize(0, args.network_interface)

    audio_client = AudioClient()
    audio_client.SetTimeout(10.0)
    audio_client.Init()

    ret = audio_client.LedControl(red, green, blue)
    if ret != 0:
        raise RuntimeError(f"LedControl failed with code: {ret}")

    print(f"[INFO] LED color set to R={red} G={green} B={blue}")

    if args.hold > 0:
        time.sleep(args.hold)

    return 0


if __name__ == "__main__":
    sys.exit(main())
