#!/bin/bash
# route.sh SLOT KEY... : select a unit, press direction keys in move mode (echoing the preview hex), confirm the move.
# Preview 00 ff = left the range and stays invalid: cancel, select again, press only the keys that were valid. The command ring is then open.
R=$(cd "$(dirname "$0")/../../.." && pwd); P=$R/.venv/bin/python
read x y < <($P $R/tools/emu/play/bt.py units | sed -n "s/^ *$1 .* x *\([0-9]*\) y *\([0-9]*\) .*/\1 \2/p")
shift; keys=("$@"); sel(){ $P $R/tools/emu/play/bt.py goto $x $y >/dev/null; sleep 1; $R/tools/emu/hpress.sh /dev/null X; sleep 2.5; }
sel; n=0; bad=0
for d in "${keys[@]}"; do
  $P $R/tools/emu/vpad.py hold $d 60 >/dev/null; sleep .5; v=$($P $R/tools/emu/ram.py read 0x800ca4ac 2); echo "$d $v"
  case "$v" in *"00 ff") bad=1; break;; esac; n=$((n+1))
done
if [ $bad = 1 ]; then
  $R/tools/emu/hpress.sh /dev/null Z; sleep 1.5; sel
  for d in "${keys[@]:0:$n}"; do $P $R/tools/emu/vpad.py hold $d 60 >/dev/null; sleep .5; done; echo "retry $n: $($P $R/tools/emu/ram.py read 0x800ca4ac 2)"
fi
$R/tools/emu/hpress.sh /dev/null X; sleep 2
