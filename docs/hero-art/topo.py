import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
rng = np.random.default_rng(4)
z = gaussian_filter(rng.normal(size=(270, 480)), 22) + 0.4*gaussian_filter(rng.normal(size=(270, 480)), 8)
fig = plt.figure(figsize=(19.2, 10.8), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off')
fig.patch.set_facecolor('#0f1116')
lv = np.linspace(z.min(), z.max(), 46)
ax.contour(z, levels=lv, colors='#5c6678', linewidths=[1.6 if i % 5 == 0 else 0.7 for i in range(len(lv))], alpha=0.8)
# route: a smooth wandering line with km dots
t = np.linspace(0, 1, 400)
x = 20 + 440*t; y = 135 + 70*np.sin(t*7) + 30*np.sin(t*17)
ax.plot(x, y, color='#FF5A1F', lw=4, solid_capstyle='round', alpha=0.9)
ax.plot(x[::40], y[::40], 'o', color='#0f1116', mec='#FF5A1F', mew=2.5, ms=11)
ax.set_xlim(0, 479); ax.set_ylim(0, 269)
fig.savefig('bg-10-route-map.png', facecolor=fig.get_facecolor())
