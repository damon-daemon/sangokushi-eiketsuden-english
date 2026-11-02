#!/bin/bash
# endphase.sh [nowait] : from a command ring: Wait, open the end-turn prompt, confirm, then wait until units and cursor are unchanged for 15 s with the cursor on Liu Bei
R=$(cd "$(dirname "$0")/../../.." && pwd); P=$R/.venv/bin/python
[ "$1" = nowait ] || { $P $R/tools/emu/vpad.py hold Down 250 >/dev/null; sleep 1.5; }
$R/tools/emu/hpress.sh /dev/null Z; sleep 1; $R/tools/emu/hpress.sh /dev/null X; sleep 8
snap(){ $P $R/tools/emu/play/bt.py units; $P $R/tools/emu/ram.py read 0x800ca488 2; }
a=$(snap); same=0
for i in $(seq 1 60); do
  sleep 3; b=$(snap); if [ "$a" = "$b" ]; then same=$((same+1)); else same=0; a=$b; fi
  read x y < <(echo "$b" | sed -n 's/^ *0 .* x *\([0-9]*\) y *\([0-9]*\) .*/\1 \2/p')
  c=$(echo "$b" | tail -1 | cut -d' ' -f3-)
  [ $same -ge 5 ] && [ "$c" = "$(printf '%02x %02x' $x $y)" ] && { echo "phase over after $i polls"; exit; }
done; echo "timeout (event or dialog?)"
