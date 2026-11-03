#!/bin/bash
# march.sh OUT.png: cursor already on the officer who asks. Question, Yes, skip save, formation (first 6 rows), confirm
cd "$(dirname "$0")/../../.."
P="tools/emu/hpress.sh /dev/null"; V=".venv/bin/python tools/emu/vpad.py hold"
$P X; sleep 3; tools/emu/hshot.sh $1.1.png; $P X; sleep 3; $P X; sleep 3; tools/emu/hshot.sh $1.2.png; $P Z; sleep 12; tools/emu/hshot.sh $1.3.png; $P X; sleep 5; $V Triangle 120 >/dev/null; sleep 3
for r in 0 1 2 3 4 5; do $P X; sleep 1; $V Down 60 >/dev/null; sleep .7; done; tools/emu/hshot.sh $1.4.png; $P Z; sleep 3; $P X; sleep 8
tools/emu/hshot.sh $1.5.png
.venv/bin/python -c "
from PIL import Image
c=Image.new('RGB',(960,480))
for i in range(5): c.paste(Image.open('$1.%d.png'%(i+1)).resize((320,240)),((i%3)*320,(i//3)*240))
c.save('$1')"
