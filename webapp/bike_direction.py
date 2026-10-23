"""Which way the bike in a photo faces: handlebars on the left or on the right.

A small neural net, trained on the catalogue photos (which all face right) pasted onto all sorts of
backgrounds, mirrored half of the time. It looks at the photo and at its mirror image and compares
the two, so a mirrored photo always gets the opposite answer. The weights are in
bike_direction.npz, made by tools/train_bike_direction.py; this runs them with numpy only.
"""
import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps

WEIGHTS = os.path.join(os.path.dirname(__file__), "bike_direction.npz")
SIZE = (128, 96)
# How sure it must be before the photo is mirrored. On 17 real photos (not used for training) the
# wrong answers scored at most 7.1 either way, all photos with several bikes or a bike behind a
# fence; the clear ones scored 10 to 30. Below this the photo is left as it is.
SURE = 10.0


@lru_cache(maxsize=1)
def _weights():
    with np.load(WEIGHTS) as w:
        return {k: w[k] for k in w.files}


def _conv(x, weight, bias):
    """3x3 convolution with padding 1, then ReLU and 2x2 max pooling. x is (channels, h, w)."""
    c, h, w = x.shape
    p = np.pad(x, ((0, 0), (1, 1), (1, 1)))
    patches = np.stack([p[:, dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)], axis=1)
    out = weight.reshape(weight.shape[0], -1) @ patches.reshape(c * 9, h * w) + bias[:, None]
    out = np.maximum(out, 0).reshape(-1, h // 2, 2, w // 2, 2)
    return out.max(axis=(2, 4))


def _evidence(a):
    """How much the photo (a 96x128 grey array, 0..1) looks like a bike facing right."""
    w = _weights()
    x = ((a - a.mean()) / (a.std() + 1e-3))[None]
    for n in range(4):
        x = _conv(x, w[f"conv{n}.weight"], w[f"conv{n}.bias"])
    return float(w["fc.weight"].ravel() @ x.ravel() + w["fc.bias"][0])


def score(img):
    """Positive: faces right (handlebars right). Negative: faces left. Near 0: can't tell."""
    a = np.asarray(ImageOps.grayscale(img).resize(SIZE, Image.BICUBIC), dtype=np.float32) / 255
    return _evidence(a) - _evidence(a[:, ::-1])


def faces_left(img):
    """True or False when it's sure, None when it isn't."""
    s = score(img)
    if abs(s) < SURE:
        return None
    return s < 0
