#!/usr/bin/env python3
"""Analyze frame sizes in b2_listing.tsv and flag potential anomalies.

Heuristics:
- Zero-byte frames are always flagged.
- Frames smaller than 20% of the local median (±window) are flagged.
- Frames below the 1st percentile are flagged as globally tiny.
- Prints top N smallest frames for quick inspection.

Usage:
    python3 analyze_tsv_frames.py              # uses b2_listing.tsv in cwd
    python3 analyze_tsv_frames.py --tsv path/to/b2_listing.tsv --window 5 --top 15
"""
from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path
from typing import List, Sequence, Tuple

PATTERN = re.compile(r"(?:.*/)?DanceOfTheSugarPlumFairy_John4K_(\d+)\s*(\(2\))?\.png$")


def load_tsv(tsv_path: Path) -> List[Tuple[str, int]]:
    if not tsv_path.exists():
        raise FileNotFoundError(f"TSV not found: {tsv_path}")
    lines = tsv_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(lines) < 2:
        raise ValueError(f"TSV is empty or header-only: {tsv_path}")
    frames: List[Tuple[str, int]] = []
    for line in lines[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, size_str = parts[0], parts[1]
        m = PATTERN.search(name)
        if not m:
            continue
        try:
            size = int(size_str)
        except ValueError:
            continue
        frames.append((name, size))
    if not frames:
        raise ValueError("No matching frames found in TSV.")
    return frames


def percentiles(values: Sequence[int], ps: Sequence[float]) -> List[float]:
    if not values:
        return [float("nan") for _ in ps]
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    results: List[float] = []
    for p in ps:
        if not 0 <= p <= 100:
            results.append(float("nan"))
            continue
        k = (p / 100) * (n - 1)
        f = int(k)
        c = min(f + 1, n - 1)
        if f == c:
            results.append(float(sorted_vals[f]))
        else:
            d0 = sorted_vals[f] * (c - k)
            d1 = sorted_vals[c] * (k - f)
            results.append(float(d0 + d1))
    return results


def local_median(values: Sequence[int], idx: int, window: int) -> float:
    lo = max(0, idx - window)
    hi = min(len(values), idx + window + 1)
    neighborhood = values[lo:hi]
    return float(statistics.median(neighborhood)) if neighborhood else float("nan")


def analyze(frames: List[Tuple[str, int]], window: int, top_n: int):
    names = [f[0] for f in frames]
    sizes = [f[1] for f in frames]

    p01, p50, p99 = percentiles(sizes, [1, 50, 99])

    zero_sizes = [(n, s) for n, s in frames if s <= 0]

    local_small = []
    for i, (name, size) in enumerate(frames):
        med = local_median(sizes, i, window)
        if med <= 0:
            continue
        if size < 0.2 * med:
            local_small.append((name, size, med))

    global_tiny = [(n, s) for n, s in frames if s < p01]

    smallest = sorted(frames, key=lambda x: x[1])[:top_n]

    print(f"Frames analyzed: {len(frames)}")
    print(f"Size percentiles: p01={p01:,.0f}, p50={p50:,.0f}, p99={p99:,.0f}")
    print()

    if zero_sizes:
        print(f"Zero-byte frames (suspect): {len(zero_sizes)}")
        for n, s in zero_sizes[:20]:
            print(f"  {n}\t{s}")
        print()

    if local_small:
        print(f"Local outliers (<20% of local median): {len(local_small)}")
        for n, s, med in local_small[:30]:
            print(f"  {n}\t{s} (local median ~ {med:,.0f})")
        print()
    else:
        print("Local outliers: none\n")

    if global_tiny:
        print(f"Global tiny (<p01={p01:,.0f}): {len(global_tiny)}")
        for n, s in global_tiny[:30]:
            print(f"  {n}\t{s}")
        print()
    else:
        print("Global tiny: none\n")

    print(f"Top {top_n} smallest frames:")
    for n, s in smallest:
        print(f"  {n}\t{s}")


def main():
    parser = argparse.ArgumentParser(description="Analyze frame sizes in b2_listing.tsv")
    parser.add_argument("--tsv", type=Path, default=Path("b2_listing.tsv"), help="Path to TSV file")
    parser.add_argument("--window", type=int, default=5, help="Half-window size for local median")
    parser.add_argument("--top", type=int, default=20, help="How many smallest frames to print")
    args = parser.parse_args()

    frames = load_tsv(args.tsv)
    analyze(frames, window=max(1, args.window), top_n=max(1, args.top))


if __name__ == "__main__":
    main()
