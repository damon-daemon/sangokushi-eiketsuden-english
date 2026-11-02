"""prompt.py shot.png : exit 0 if the grey 'End all units' commands?' box is on screen (grey pixels along y=75..80, x=40..60)"""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB')
grey = 0
for x in range(40, 60):
    for y in range(74, 80):
        r, g, b = im.getpixel((x, y))
        if abs(r - g) < 12 and abs(g - b) < 12 and 40 < r < 120: grey += 1
sys.exit(0 if grey > 80 else 1)
