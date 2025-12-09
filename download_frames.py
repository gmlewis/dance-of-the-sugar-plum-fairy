#!/usr/bin/env python3
"""Download specific frames from Backblaze B2 by frame number.

Usage:
    python3 download_frames.py 2127 2128 2129

- Reads B2 credentials from .env.development.local (not printed).
- Optional env: B2_PREFIX to look under a prefix.
- Downloads into the current directory, naming files exactly as in the bucket.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List

try:
    from b2sdk.v2 import B2Api, InMemoryAccountInfo
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("Missing dependency b2sdk. Install with: pip install b2sdk\n")
    raise

REQUIRED_ENV = ["B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME"]
DEFAULT_ENV_FILE = Path(".env.development.local")
FILENAME_TEMPLATE = "DanceOfTheSugarPlumFairy_John4K_{:04d}.png"


def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


def ensure_keys(env: Dict[str, str], required: Iterable[str]) -> None:
    missing = [k for k in required if k not in env or not env[k]]
    if missing:
        names = ", ".join(missing)
        available = ", ".join(sorted(env.keys())) if env else "none"
        raise KeyError(f"Missing required env vars: {names}. Found keys: {available}")


def apply_env(env: Dict[str, str], required: Iterable[str]) -> Dict[str, str]:
    merged = dict(os.environ)
    merged.update(env)
    for key in required:
        if key in env and env[key] and key not in os.environ:
            os.environ[key] = env[key]
    return merged


def download_files(env: Dict[str, str], frame_numbers: List[int]) -> None:
    info = InMemoryAccountInfo()
    api = B2Api(info)
    api.authorize_account("production", env["B2_APPLICATION_KEY_ID"], env["B2_APPLICATION_KEY"])
    bucket = api.get_bucket_by_name(env["B2_BUCKET_NAME"])

    prefix = env.get("B2_PREFIX") or ""
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    for num in frame_numbers:
        filename = FILENAME_TEMPLATE.format(num)
        remote_name = f"{prefix}{filename}"
        dest_path = Path(filename)
        try:
            bucket.download_file_by_name(remote_name).save_to(dest_path)
            print(f"Downloaded: {remote_name} -> {dest_path}")
        except Exception as exc:
            print(f"Failed: {remote_name} ({exc})")


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python3 download_frames.py <frame_num> [frame_num ...]\n")
        sys.exit(1)

    try:
        frame_numbers = [int(arg) for arg in sys.argv[1:]]
    except ValueError:
        sys.stderr.write("Frame numbers must be integers.\n")
        sys.exit(1)

    env_path = DEFAULT_ENV_FILE
    try:
        env_file = load_env_file(env_path)
        env = apply_env(env_file, REQUIRED_ENV)
        ensure_keys(env, REQUIRED_ENV)
    except Exception as exc:
        sys.stderr.write(f"Env error: {exc}\n")
        sys.exit(1)

    download_files(env, frame_numbers)


if __name__ == "__main__":
    main()
