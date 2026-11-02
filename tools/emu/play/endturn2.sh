#!/bin/bash
# endturn2.sh N : N times: open the end-turn prompt (verified by screenshot), confirm, wait for the enemy phase, weaken + heal
R=$(cd "$(dirname "$0")/../../.." && pwd); SP=$(dirname "$0"); P=$R/.venv/bin/python
cur(){ $P $R/tools/emu/ram.py read 0x800ca488 2 | awk '{printf "%d %d", strtonum("0x"$2), strtonum("0x"$3)}'; }
for t in $(seq 1 $1); do
  ok=0
  for try in 1 2 3; do
    $R/tools/emu/hpress.sh $SP/_p.png Z w
    if $P $SP/prompt.py $SP/_p.png; then ok=1; break; fi
  done
  [ $ok = 1 ] || { echo "no prompt"; break; }
  $R/tools/emu/hpress.sh /dev/null X
  sleep 12
  pos=$($P $SP/bt.py units | head -1 | sed 's/.*x *\([0-9]*\) y *\([0-9]*\).*/\1 \2/')
  for i in $(seq 1 40); do
    c=$(cur); sleep 2
    [ "$c" = "$pos" ] && [ "$(cur)" = "$pos" ] && break
  done
  echo "== turn $t done after $i polls"
  $P $SP/bt.py units | grep " E " | grep -v 'x 255' | awk '{print $1, $4, $5, $6, $7, $8, $9, $10, $11, $12}' | head -3
  $P $SP/bt.py weaken; for s in 0 1 2 3 4 5 6; do $P $SP/bt.py hp $s 400; done
done
$R/tools/emu/hshot.sh $SP/end.png
