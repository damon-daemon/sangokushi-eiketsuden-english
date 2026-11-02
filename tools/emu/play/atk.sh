#!/bin/bash
# atk.sh SLOT MOVEKEYS... -- TARGETKEY : move a unit, choose Attack, step to the target, hit it
R=$(cd "$(dirname "$0")/../../.." && pwd); P=$R/.venv/bin/python
s=$1; shift; m=(); while [ "$1" != "--" ]; do m+=("$1"); shift; done; shift
$R/tools/emu/play/route.sh $s "${m[@]}"
$P $R/tools/emu/vpad.py hold Up 250 >/dev/null; sleep 1.5
for k in "$@"; do $P $R/tools/emu/vpad.py hold $k 60 >/dev/null; sleep .6; done
$R/tools/emu/hpress.sh /dev/null X; sleep 10
