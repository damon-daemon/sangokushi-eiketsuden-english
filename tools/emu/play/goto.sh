#!/bin/bash
# goto.sh CHAPTER SECTION [BLOCK [ENTRY]] : with the headless emulator running on sstates/s13_ch2_start.sav (narration up), jump there (jump.py)
R=$(cd "$(dirname "$0")/../../.." && pwd); cd $R
(timeout 40 .venv/bin/python -u tools/emu/play/jump.py $1 ${2:-0} $3 $4 > /dev/null 2>&1 &)
sleep 2; for i in 1 2 3 4 5 6; do tools/emu/hpress.sh /dev/null x; sleep 2; done; sleep 8
.venv/bin/python tools/emu/ram.py read 0x80178880 8
