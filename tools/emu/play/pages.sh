#!/bin/bash
# pages.sh PREFIX N [key] : tap Circle (or key) N times, screenshot after each; keep changed ones; contact sheet PREFIX_sheet.png
cd "$(dirname "$0")/../../.."
P=${1:?}; N=$2; K=${3:-x}; prev=; rm -f "${P}"_[0-9]*.png
for i in $(seq 1 $N); do
  tools/emu/hpress.sh ${P}_$i.png $K w >/dev/null
  h=$(md5sum < ${P}_$i.png)
  if [ "$h" = "$prev" ]; then rm ${P}_$i.png; fi
  prev=$h
done
.venv/bin/python $(dirname $0)/sheet.py $P
