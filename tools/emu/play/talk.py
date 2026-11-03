#!/usr/bin/env python3
"""talk.py PREFIX MAX [cursor keys...]: tap Circle until the screen settles with no text box (a box-free frame nearly equal to an earlier
box-free frame seen after a tap), keep every distinct frame, contact sheet. If a hall is idle, first tap the cursor keys. Leaves no box open."""
import sys,subprocess,time,glob,os
from PIL import Image,ImageChops
R=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(R); pre=sys.argv[1]; mx=int(sys.argv[2]); keys=sys.argv[3:]
for f in glob.glob(pre+'_*.png'): os.remove(f)
PY=R+'/.venv/bin/python'
def hold(k,ms): subprocess.run([PY,'tools/emu/vpad.py','hold',k,str(ms)],stdout=subprocess.DEVNULL)
def shot(p): subprocess.run(['tools/emu/hshot.sh',p],stdout=subprocess.DEVNULL); return Image.open(p).convert('RGB')
def box(im):  # dark red text-box body anywhere, top or bottom
    w,h=im.size; n=0;t=0
    for y in list(range(20,60,4))+list(range(170,230,4)):
        for x in range(70,300,6):
            r,g,b=im.getpixel((x*w//320,y*h//240)); t+=1
            if r>90 and g<45 and b<45: n+=1
    return n/t>0.25
def same(a,b):
    d=ImageChops.difference(a,b).convert('L').point(lambda v:255 if v>24 else 0)
    return sum(d.histogram()[255:])<a.size[0]*a.size[1]*0.02
time.sleep(1.5)
for k in keys: hold(k,60); time.sleep(1)
idle=[];i=0;kept=None;quiet=0
for n in range(mx):
    hold('Circle',40); time.sleep(1.4)
    p='%s_%d.png'%(pre,n+1); im=shot(p)
    if kept is not None and same(im,kept): os.remove(p)
    else: kept=im
    if box(im): quiet=0; continue
    # no box: did it settle?
    if any(same(im,o) for o in idle): quiet+=1
    else: idle.append(im)
    if quiet>=1: break
subprocess.run([PY,'tools/emu/play/sheet.py',pre])
print(subprocess.run([PY,'tools/emu/ram.py','read','0x80178880','8'],capture_output=True,text=True).stdout.strip(),'taps',n+1,'box',box(im))
