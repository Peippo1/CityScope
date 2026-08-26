#!/usr/bin/env python3
"""Build the static web app while forwarding only public root configuration."""

from __future__ import annotations

import os
import subprocess

from dev import ROOT, public_web_environment


def main() -> int:
    environment = public_web_environment(ROOT / ".env.local", os.environ)
    return subprocess.call(["npm", "run", "build"], cwd=ROOT / "apps" / "web", env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
