#!/usr/bin/env python3
"""List Backblaze B2 frames and report missing/duplicate frames.

This script loads secrets from .env.development.local (not printed), authenticates
against Backblaze B2, lists all matching frame files, and reports:
- First/last frame numbers
- Missing frame numbers between first and last
- Duplicate frames (including those with a "(2)" suffix) with sizes to spot anomalies

Optional env: B2_PREFIX to list only files under that prefix (e.g., "renders/").

Requirements: pip install b2sdk

Usage:
    python3 find_frames_b2.py               # uses .env.development.local in cwd
    python3 find_frames_b2.py /path/to/.env # override env file location
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

try:
    from b2sdk.v2 import B2Api, InMemoryAccountInfo
except ImportError as exc:  # pragma: no cover - dependency hint
    sys.stderr.write(
        "Missing dependency b2sdk. Install with: pip install b2sdk\n"
    )
    raise

PATTERN = re.compile(
    r"(?:.*/)?(DanceOfTheSugarPlumFairy_John4K_)(\d+)(\s*\(2\))?\.png$",
)


def load_env_file(path: Path) -> Dict[str, str]:
    """Load a minimal .env file without printing secrets."""
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
        raise KeyError(
            f"Missing required env vars: {names}. Found keys: {available}"
        )


def apply_env(env: Dict[str, str], required: Iterable[str]) -> Dict[str, str]:
    """Merge file env with process env and export required keys to os.environ."""
    merged = dict(os.environ)
    merged.update(env)
    for key in required:
        if key in env and env[key] and key not in os.environ:
            os.environ[key] = env[key]
    return merged


def list_b2_files(env: Dict[str, str], prefix: str | None = None) -> List[Tuple[str, int, int]]:
    """Return a list of (file_name, size_bytes, upload_timestamp_ms) for all files in the bucket."""
    info = InMemoryAccountInfo()
    api = B2Api(info)
    api.authorize_account("production", env["B2_APPLICATION_KEY_ID"], env["B2_APPLICATION_KEY"])
    bucket = api.get_bucket_by_name(env["B2_BUCKET_NAME"])

    kwargs = {"prefix": prefix} if prefix else {}

    files: List[Tuple[str, int, int]] = []
    for file_version, _ in bucket.ls(**kwargs):
        if file_version is None:
            continue
        files.append((file_version.file_name, file_version.size, file_version.upload_timestamp))
    return files


def analyze_frames(files: Sequence[Tuple[str, int, int]]):
    """Analyze matching frames, returning summary data."""
    matches = []
    for name, size, _ts in files:
        m = PATTERN.search(name)
        if not m:
            continue
        digits = m.group(2)
        number = int(digits)
        has_suffix = bool(m.group(3))
        matches.append({
            "name": name,
            "number": number,
            "digits": digits,
            "size": size,
            "has_suffix": has_suffix,
        })

    if not matches:
        return None

    matches_sorted = sorted(matches, key=lambda x: x["number"])
    first = matches_sorted[0]
    last = matches_sorted[-1]
    width = max(len(m["digits"]) for m in matches_sorted)

    present = {}
    for m in matches_sorted:
        present.setdefault(m["number"], []).append(m)

    missing = [n for n in range(first["number"], last["number"] + 1) if n not in present]

    duplicates = {num: items for num, items in present.items() if len(items) > 1}

    return {
        "first": first,
        "last": last,
        "width": width,
        "missing": missing,
        "duplicates": duplicates,
        "matched_count": len(matches_sorted),
    }


def write_tsv(path: Path, files: Sequence[Tuple[str, int, int]]) -> None:
    """Write a TSV with filename, size_bytes, upload_timestamp_ms, upload_timestamp_iso."""
    lines = ["filename\tsize_bytes\tupload_timestamp_ms\tupload_timestamp_iso\n"]
    for name, size, ts_ms in files:
        iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
        lines.append(f"{name}\t{size}\t{ts_ms}\t{iso}\n")
    path.write_text("".join(lines), encoding="utf-8")


def format_frame(n: int, width: int) -> str:
    return str(n).zfill(width)


def main():
    env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".env.development.local")
    try:
        env_file = load_env_file(env_path)
        required = ["B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY", "B2_BUCKET_NAME"]
        env = apply_env(env_file, required)
        ensure_keys(env, required)
    except Exception as exc:  # pragma: no cover - setup errors
        sys.stderr.write(f"Env error: {exc}\n")
        sys.exit(1)

    try:
        prefix = env.get("B2_PREFIX") or None
        files = list_b2_files(env, prefix=prefix)
    except Exception as exc:  # pragma: no cover - network/API errors
        sys.stderr.write(f"B2 error: {exc}\n")
        sys.exit(1)

    total_files = len(files)
    tsv_path = Path("b2_listing.tsv")
    try:
        write_tsv(tsv_path, files)
    except Exception as exc:
        sys.stderr.write(f"TSV write error: {exc}\n")
        # continue to analysis even if TSV fails
    summary = analyze_frames(files)
    if summary is None:
        print("No matching frames found in bucket.")
        print(f"Total files scanned: {total_files}")
        sample = ", ".join(name for name, _, _ in files[:10]) if files else "(bucket empty)"
        print(f"Sample names: {sample}")
        print(f"TSV written to: {tsv_path}")
        return

    first = summary["first"]
    last = summary["last"]
    width = summary["width"]
    missing = summary["missing"]
    duplicates = summary["duplicates"]

    print(f"Scanned files: {total_files}")
    print(f"Matched frames: {summary['matched_count']}")
    print(f"First frame: {format_frame(first['number'], width)} ({first['name']}, {first['size']} bytes)")
    print(f"Last frame:  {format_frame(last['number'], width)} ({last['name']}, {last['size']} bytes)")
    print(f"TSV written to: {tsv_path}")

    if missing:
        missing_str = ", ".join(format_frame(n, width) for n in missing)
        print(f"Missing frames: {missing_str}")
    else:
        print("Missing frames: none")

    if duplicates:
        print("Duplicates / suspicious entries:")
        for num in sorted(duplicates):
            entries = duplicates[num]
            label = format_frame(num, width)
            parts = [f"{e['name']} ({e['size']} bytes)" for e in entries]
            print(f"  {label}: " + " | ".join(parts))
    else:
        print("Duplicates / suspicious entries: none")


if __name__ == "__main__":
    main()
