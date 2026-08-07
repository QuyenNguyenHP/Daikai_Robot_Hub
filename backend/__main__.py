"""Command-line entry point for the FaceLens backend."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 backend",
        description="Start FaceLens with the network interface connected to the robot.",
    )
    parser.add_argument(
        "network_interface",
        help="Robot network interface, for example eth10",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Address on which the API listens (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API port (default: 8000)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be between 1 and 65535")

    # Set this before importing backend.main so every Unitree service receives
    # the selected interface when FastAPI creates its lifespan resources.
    os.environ["UNITREE_NETWORK_INTERFACE"] = args.network_interface

    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        workers=1,
    )


if __name__ == "__main__":
    main()

