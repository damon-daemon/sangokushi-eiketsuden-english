import sys, glob, re
from PIL import Image
pre = sys.argv[1]
fs = sorted((f for f in glob.glob(pre + '_*.png') if re.search(r'_\d+\.png$', f)), key=lambda f: int(re.search(r'_(\d+)\.png$', f).group(1)))
ims = [Image.open(f) for f in fs]
if not ims: print('none'); sys.exit()
w, h = ims[0].size; cols = 3; rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (w * cols, h * rows))
for i, im in enumerate(ims): sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(pre + '_sheet.png'); print(len(ims), 'pages')
