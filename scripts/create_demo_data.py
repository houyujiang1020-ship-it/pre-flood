from pathlib import Path
import numpy as np
from PIL import Image

root = Path(__file__).resolve().parents[1] / "data" / "demo"
root.mkdir(parents=True, exist_ok=True)
pre = np.full((256, 256, 3), (190, 185, 165), dtype=np.uint8)
pre[30:230:24, :] = (80, 80, 80)
pre[:, 25:240:32] = (95, 95, 95)
post = pre.copy()
y, x = np.ogrid[:256, :256]
flood = ((x - 135) ** 2 / 95**2 + (y - 145) ** 2 / 75**2) <= 1
post[flood] = (35, 75, 175)
Image.fromarray(pre).save(root / "灾前演示.png")
Image.fromarray(post).save(root / "灾后演示.png")
print(root)
