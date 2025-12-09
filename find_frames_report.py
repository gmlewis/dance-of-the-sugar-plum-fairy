#!/usr/bin/env python3
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"DetailsDanceOfTheSugarPlumFairy_John4K_(\d+)\.png")


def parse_frames(text: str):
    matches = []
    for match in PATTERN.finditer(text):
        digit_text = match.group(1)
        matches.append((match.group(0), int(digit_text), digit_text))
    return matches


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("backblaze.txt")
    if not path.exists():
        sys.stderr.write(f"File not found: {path}\n")
        sys.exit(1)

    text = path.read_text(encoding="utf-8", errors="ignore")
    matches = parse_frames(text)
    if not matches:
        print("No matching frames found.")
        return

    first_str, first_num, first_digits = matches[0]
    last_str, last_num, last_digits = matches[-1]

    width = max(len(first_digits), len(last_digits), max(len(d) for _, _, d in matches))

    present_numbers = {num for _, num, _ in matches}
    missing = [n for n in range(first_num, last_num + 1) if n not in present_numbers]

    print(f"First frame: {str(first_num).zfill(width)}")
    print(f"Last frame: {str(last_num).zfill(width)}")
    if missing:
        missing_formatted = ", ".join(str(n).zfill(width) for n in missing)
        print(f"Missing frames: {missing_formatted}")
    else:
        print("Missing frames: none")


if __name__ == "__main__":
    main()
