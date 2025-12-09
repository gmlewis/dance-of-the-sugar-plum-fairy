#!/usr/bin/env python3
"""Upload new rendered frames to Backblaze B2.

Workflow:
- Load secrets from .env.development.local (not printed).
- Read b2_listing.tsv to know which files already exist in the bucket.
- Scan local JohnPNG/ for non-zero-length PNGs matching the frame pattern.
- Upload only those not present in b2_listing.tsv.

Optional env: B2_PREFIX to upload under a prefix (e.g., "renders/").
Requirements: pip install b2sdk
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

try:
    from b2sdk.v2 import B2Api, InMemoryAccountInfo
except ImportError as exc:  # pragma: no cover
    sys.stderr.write("Missing dependency b2sdk. Install with: pip install b2sdk\n")
    raise

PATTERN = re.compile(r"(?:.*/)?(DanceOfTheSugarPlumFairy_John4K_)(\d+)(\s*\(2\))?\.png$")
REQUIRED_ENV = ["B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME"]
DEFAULT_ENV_FILE = Path(".env.development.local")
LISTING_FILE = Path("b2_listing.tsv")
LOCAL_DIR = Path("JohnPNG")


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


def read_listing(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    names: Set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[1:]:
        parts = line.split("\t")
        if parts:
            names.add(parts[0])
    return names


def list_local_frames(directory: Path) -> List[Tuple[Path, str, int]]:
    if not directory.exists():
        raise FileNotFoundError(f"Local directory not found: {directory}")
    results: List[Tuple[Path, str, int]] = []
    for path in sorted(directory.glob("*.png")):
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size <= 0:
            continue  # ignore zero-length placeholder files
        m = PATTERN.match(path.name)
        if not m:
            continue
        results.append((path, path.name, size))
    return results


def build_remote_name(prefix: str | None, filename: str) -> str:
    if not prefix:
        return filename
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    return prefix + filename


def upload_files(env: Dict[str, str], uploads: List[Tuple[Path, str]]) -> None:
    info = InMemoryAccountInfo()
    api = B2Api(info)
    api.authorize_account("production", env["B2_APPLICATION_KEY_ID"], env["B2_APPLICATION_KEY"])
    bucket = api.get_bucket_by_name(env["B2_BUCKET_NAME"])

    for local_path, remote_name in uploads:
        bucket.upload_local_file(
            local_file=str(local_path),
            file_name=remote_name,
            content_type="image/png",
        )
        print(f"Uploaded: {local_path} -> {remote_name}")


def main():
    env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ENV_FILE
    try:
        env_file = load_env_file(env_path)
        env = apply_env(env_file, REQUIRED_ENV)
        ensure_keys(env, REQUIRED_ENV)
    except Exception as exc:
        sys.stderr.write(f"Env error: {exc}\n")
        sys.exit(1)

    try:
        existing = read_listing(LISTING_FILE)
    except Exception as exc:
        sys.stderr.write(f"Listing read error: {exc}\n")
        sys.exit(1)

    try:
        local_frames = list_local_frames(LOCAL_DIR)
    except Exception as exc:
        sys.stderr.write(f"Local scan error: {exc}\n")
        sys.exit(1)

    prefix = env.get("B2_PREFIX") or None
    uploads: List[Tuple[Path, str]] = []
    for path, name, _size in local_frames:
        remote_name = build_remote_name(prefix, name)
        if remote_name in existing:
            continue
        uploads.append((path, remote_name))

    print(f"Local frames found (non-zero, matching pattern): {len(local_frames)}")
    print(f"Already in bucket listing: {len(existing)}")
    print(f"New files to upload: {len(uploads)}")

    if not uploads:
        print("Nothing to upload.")
        return

    try:
        upload_files(env, uploads)
    except Exception as exc:
        sys.stderr.write(f"Upload error: {exc}\n")
        sys.exit(1)

    print("Upload complete.")


if __name__ == "__main__":
    main()
