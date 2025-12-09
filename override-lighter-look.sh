#!/bin/bash -ex
# For "lighter" look (add a neutral/untagged equivalent, e.g., raw linear)
for f in DanceOfTheSugarPlumFairy_EVEE_v41_*.exr; do
    oiiotool "$f" --eraseattrib colorInteropID -o "light_$f"
done
