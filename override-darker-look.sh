#!/bin/bash -ex
# For "darker" look (add colorInteropID: "lin_rec709_scene" like your tagged files)
for f in DanceOfTheSugarPlumFairy_EVEE_v41_*.exr; do
    [ -f "dark_$f" ] && echo "Skipping $f (dark_$f exists)" && continue
    oiiotool --threads 16 "$f" --sattrib colorInteropID "lin_rec709_scene" -o "dark_$f"
done
