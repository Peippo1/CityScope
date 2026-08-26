#!/usr/bin/env python3
"""Run the CityScope web, API, and MCP development services together."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Mapping

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]


def process_specs() -> list[tuple[str, list[str], Path]]:
    python = sys.executable
    return [
        ("City Data MCP", [python, "-m", "uvicorn", "services.city_data_mcp.server:app", "--reload", "--port", "8001"], ROOT),
        ("City Live Data MCP", [python, "-m", "uvicorn", "services.city_live_data_mcp.server:app", "--reload", "--port", "8002"], ROOT),
        ("CityScope API", [python, "-m", "uvicorn", "apps.api.app.main:app", "--reload", "--port", "8000"], ROOT),
        ("CityScope web", ["npm", "run", "dev"], ROOT / "apps" / "web"),
    ]


def validate_environment() -> None:
    if importlib.util.find_spec("uvicorn") is None:
        raise RuntimeError("Uvicorn is unavailable. Activate the project virtual environment and install .[dev].")
    if shutil.which("npm") is None:
        raise RuntimeError("npm is unavailable. Install Node.js 20 or newer.")
    if not (ROOT / "apps" / "web" / "node_modules").exists():
        raise RuntimeError("Web dependencies are unavailable. Run npm install in apps/web.")


def public_web_environment(env_file: Path, base: Mapping[str, str]) -> dict[str, str]:
    environment = dict(base)
    for name, value in dotenv_values(env_file, interpolate=False).items():
        if name.startswith("NEXT_PUBLIC_") and value:
            environment.setdefault(name, value)
    return environment


def stop_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    for process in processes:
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)


def main() -> int:
    validate_environment()
    processes: list[subprocess.Popen[bytes]] = []
    try:
        for name, command, cwd in process_specs():
            print(f"Starting {name}...", flush=True)
            environment = public_web_environment(ROOT / ".env.local", os.environ) if name == "CityScope web" else None
            processes.append(subprocess.Popen(command, cwd=cwd, env=environment, start_new_session=True))
        while True:
            for process, (name, _, _) in zip(processes, process_specs(), strict=True):
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(f"{name} exited with status {return_code}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
