"""Train the net behind webapp/bike_direction.py and write webapp/bike_direction.npz.

    pip install torch            # only needed here, not on the server
    python tools/train_bike_direction.py [--samples 36000] [--epochs 3]

Training photos are made from the catalogue photos in images/: each product shot (a side view on a
plain light ground, so always facing right) is cut out and pasted onto a made-up background (lines
like planks and fences, blurry colour noise, a blurred piece of another photo, sometimes a floor),
sometimes with other bikes behind it facing either way, then sized, shifted, tilted a little and
given a different contrast. Half of them are mirrored while training, and the net learns which.

The net compares a photo with its mirror image (score = f(photo) - f(mirrored photo)), so a mirrored
photo always gets exactly the opposite score.
"""
import argparse
import glob
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SIZE = (128, 96)


def cutout(path):
    """The bike from a product shot and its mask, or None when the photo isn't one."""
    c = Image.open(path).convert("RGB")
    c.thumbnail((700, 700))
    a = np.asarray(c, dtype=np.float32)
    corners = np.concatenate([a[:4, :4].reshape(-1, 3), a[:4, -4:].reshape(-1, 3),
                              a[-4:, :4].reshape(-1, 3), a[-4:, -4:].reshape(-1, 3)])
    if corners.std(0).max() > 6 or corners.mean() < 200:
        return None  # only shots on a plain light ground
    mask = np.abs(a - np.median(corners, 0)).max(2) > 22
    rows, cols = np.flatnonzero(mask.any(1)), np.flatnonzero(mask.any(0))
    if len(rows) < 20 or len(cols) < 20:
        return None
    box = (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1)
    if box[2] - box[0] < 1.2 * (box[3] - box[1]):
        return None  # not a side view
    m = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1))
    return c.crop(box), m.crop(box)


def background(w, h, files):
    kind = random.random()
    if kind < 0.3:  # planks, fences, bricks
        bg = Image.new("RGB", (w, h), tuple(random.randint(40, 230) for _ in range(3)))
        d = ImageDraw.Draw(bg)
        for _ in range(random.randint(0, 40)):
            x, y = random.randint(0, w), random.randint(0, h)
            colour = tuple(random.randint(30, 240) for _ in range(3))
            if random.random() < 0.5:
                d.line((x, 0, x + random.randint(-50, 50), h), fill=colour, width=random.randint(1, 8))
            else:
                d.line((0, y, w, y + random.randint(-30, 30)), fill=colour, width=random.randint(1, 8))
    elif kind < 0.6:  # blurry colour noise
        noise = (np.random.rand(h // 8 + 1, w // 8 + 1, 3) * 255).astype(np.uint8)
        bg = Image.fromarray(noise).resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(random.uniform(0, 6)))
    else:  # another photo on its side, blurred: clutter without a bike facing either way
        other = Image.open(random.choice(files)).convert("RGB").resize((w, h)).rotate(random.choice([90, 270]))
        bg = ImageEnhance.Brightness(other.filter(ImageFilter.GaussianBlur(random.uniform(0, 4)))).enhance(random.uniform(0.4, 1.0))
    if random.random() < 0.5:  # a floor
        y = int(h * random.uniform(0.6, 0.9))
        ImageDraw.Draw(bg).rectangle((0, y, w, h), fill=tuple(random.randint(40, 200) for _ in range(3)))
    return bg


def sample(files, others=0.22):
    while not (got := cutout(random.choice(files))):
        pass
    bike, mask = got
    w, h = random.choice([(400, 300), (300, 400), (400, 225), (400, 400)])
    bw = int(w * random.uniform(0.5, 1.15))
    bh = int(bw * bike.height / bike.width)
    bike, mask = bike.resize((bw, bh)), mask.resize((bw, bh))
    bg = background(w, h, files)
    if random.random() < others:  # other bikes behind it, either way round (shops, expos, sheds)
        for _ in range(random.randint(1, 3)):
            if not (got := cutout(random.choice(files))):
                continue
            ob, om = got
            if random.random() < 0.5:
                ob, om = ImageOps.mirror(ob), ImageOps.mirror(om)
            ow = int(bw * random.uniform(0.4, 0.9))
            oh = int(ow * ob.height / ob.width)
            ob = ob.resize((ow, oh)).filter(ImageFilter.GaussianBlur(random.uniform(0, 2.5)))
            bg.paste(ob, (random.randint(-ow // 2, w - ow // 2), random.randint(-oh // 3, h - oh // 2)), om.resize((ow, oh)))
    x = random.randint(min(0, w - bw), max(0, w - bw))
    y = random.randint(int(h * 0.05) - bh // 4, max(int(h * 0.05), h - bh + bh // 6))
    bg.paste(bike, (x, y), mask)
    img = ImageEnhance.Contrast(bg.rotate(random.uniform(-6, 6), resample=Image.BILINEAR)).enhance(random.uniform(0.6, 1.3))
    if random.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.5, 1.5)))
    return np.asarray(ImageOps.grayscale(img).resize(SIZE, Image.BICUBIC))


def train(photos, epochs):
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class Net(nn.Module):  # webapp/bike_direction.py runs the same layers with numpy
        def __init__(self):
            super().__init__()
            self.conv = nn.ModuleList([nn.Conv2d(1, 12, 3, padding=1), nn.Conv2d(12, 24, 3, padding=1),
                                       nn.Conv2d(24, 32, 3, padding=1), nn.Conv2d(32, 32, 3, padding=1)])
            self.fc = nn.Linear(32 * 6 * 8, 1)

        def evidence(self, x):
            x = (x - x.mean((2, 3), keepdim=True)) / (x.std((2, 3), keepdim=True) + 1e-3)
            for conv in self.conv:
                x = F.max_pool2d(F.relu(conv(x)), 2)
            return self.fc(x.flatten(1))[:, 0]

        def forward(self, x):
            return self.evidence(x) - self.evidence(x.flip(3))

    torch.manual_seed(0)
    x_all = torch.tensor(photos.astype(np.float32) / 255)[:, None]
    val, tr = x_all[: len(x_all) // 10], x_all[len(x_all) // 10:]
    net = Net()
    opt = torch.optim.Adam(net.parameters(), 2e-3, weight_decay=1e-4)
    for epoch in range(epochs):
        net.train()
        order = torch.randperm(len(tr))
        for i in range(0, len(tr), 64):
            x = tr[order[i:i + 64]]
            mirrored = torch.rand(len(x)) < 0.5
            x = torch.where(mirrored[:, None, None, None], x.flip(3), x)
            x = x * (0.6 + 0.8 * torch.rand(len(x), 1, 1, 1)) + 0.2 * (torch.rand(len(x), 1, 1, 1) - 0.5)
            inverted = torch.rand(len(x)) < 0.2
            x = torch.where(inverted[:, None, None, None], 1 - x, x)
            loss = F.binary_cross_entropy_with_logits(net(x), (~mirrored).float())
            opt.zero_grad()
            loss.backward()
            opt.step()
        net.eval()
        with torch.no_grad():
            print(f"epoch {epoch}: right on {(net(val) > 0).float().mean().item():.1%} of held-back photos", flush=True)
    return {k.replace("conv.", "conv", 1): v.numpy().astype(np.float32) for k, v in net.state_dict().items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--samples", type=int, default=36000)
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    random.seed(0)
    np.random.seed(0)
    files = glob.glob(os.path.join(ROOT, "images", "**", "*.jpg"), recursive=True)
    photos = np.array([sample(files) for _ in range(args.samples)], dtype=np.uint8)
    np.savez(os.path.join(ROOT, "webapp", "bike_direction.npz"), **train(photos, args.epochs))


if __name__ == "__main__":
    main()
