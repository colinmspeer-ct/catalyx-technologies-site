#!/usr/bin/env python3
"""Regenerate WebP/PNG logos, favicon, and the Open Graph image.

Source PNGs are the files supplied with the site brief (transparent RGBA).
Requires Pillow. Not run in CI; the optimized files are committed under src/assets.
"""

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
OUT = ROOT / "src" / "assets" / "img"
FONT_REG = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"

# Brand. Button/text blue in the live CSS is #2A7DB8; the OG card uses it for large type.
BLUE = (79, 163, 220, 255)  # #4FA3DC
BLUE_D = (42, 125, 184, 255)  # #2A7DB8
SLATE = (15, 27, 42, 255)  # #0F1B2A
SLATE_2 = (51, 65, 85, 255)  # #334155
HERO_BG = (245, 250, 254, 255)  # #F5FAFE


def content_bbox(im: Image.Image, pad: int = 0) -> tuple[int, int, int, int]:
    rgba = im.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    minx, miny, maxx, maxy = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 20 and (r + g + b) > 30:
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
    return (
        max(0, minx - pad),
        max(0, miny - pad),
        min(w, maxx + 1 + pad),
        min(h, maxy + 1 + pad),
    )


def largest_component(im: Image.Image) -> Image.Image:
    """Keep the largest opaque shape. The molecule C is one mesh; letters are separate."""
    rgba = im.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    seen = bytearray(w * h)
    best = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i]:
                continue
            r, g, b, a = px[x, y]
            if a < 40 or r + g + b < 40:
                seen[i] = 1
                continue
            q = deque([(x, y)])
            seen[i] = 1
            cells = []
            while q:
                cx, cy = q.popleft()
                cells.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= w or ny >= h:
                        continue
                    j = ny * w + nx
                    if seen[j]:
                        continue
                    rr, gg, bb, aa = px[nx, ny]
                    if aa < 40 or rr + gg + bb < 40:
                        seen[j] = 1
                        continue
                    seen[j] = 1
                    q.append((nx, ny))
            if len(cells) > len(best):
                best = cells
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    opx = out.load()
    for x, y in best:
        opx[x, y] = px[x, y]
    return out


def resized(im: Image.Image, width: int) -> Image.Image:
    if im.width == width:
        return im
    height = max(1, round(im.height * width / im.width))
    return im.resize((width, height), Image.Resampling.LANCZOS)


def save_logo(im: Image.Image, stem: str) -> None:
    im = im.convert("RGBA")
    png = OUT / f"{stem}.png"
    webp = OUT / f"{stem}.webp"
    im.save(png, "PNG", optimize=True)
    im.save(webp, "WEBP", lossless=True, quality=100, method=6)
    print(f"{stem}: {im.size}  png={png.stat().st_size}  webp={webp.stat().st_size}")


def fit(im: Image.Image, box: int, padding: int) -> Image.Image:
    """Scale im to fit in a square of `box` with transparent padding."""
    inner = box - padding * 2
    scale = min(inner / im.width, inner / im.height)
    size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
    resized = im.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    canvas.paste(resized, ((box - size[0]) // 2, (box - size[1]) // 2), resized)
    return canvas


def make_favicon(mark: Image.Image) -> None:
    master = fit(mark, 512, 48)
    ico_sizes = []
    for size in (16, 32, 48):
        ico_sizes.append(master.resize((size, size), Image.Resampling.LANCZOS))
    ico_sizes[-1].save(
        ROOT / "src" / "assets" / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=ico_sizes[:-1],
    )
    ico_sizes[1].save(OUT / "favicon-32.png", "PNG", optimize=True)
    master.resize((192, 192), Image.Resampling.LANCZOS).save(OUT / "favicon-192.png", "PNG", optimize=True)

    apple = Image.new("RGBA", (180, 180), (255, 255, 255, 255))
    icon = fit(mark, 180, 28)
    apple.paste(icon, (0, 0), icon)
    apple.convert("RGB").save(OUT / "apple-touch-icon.png", "PNG", optimize=True)
    print("favicon written")


def make_og(wordmark: Image.Image, mark: Image.Image) -> None:
    w, h = 1200, 630
    canvas = Image.new("RGBA", (w, h), HERO_BG)
    # Faint molecule mark on the right, matching the home-page watermark.
    ghost = mark.copy()
    ghost_h = 560
    ghost_w = round(mark.width * ghost_h / mark.height)
    ghost = ghost.resize((ghost_w, ghost_h), Image.Resampling.LANCZOS)
    # Lower the alpha of every pixel.
    pixels = ghost.load()
    for y in range(ghost.height):
        for x in range(ghost.width):
            r, g, b, a = pixels[x, y]
            pixels[x, y] = (r, g, b, int(a * 0.16))
    canvas.paste(ghost, (w - ghost_w + 40, (h - ghost_h) // 2), ghost)

    wm_h = 132
    wm_w = round(wordmark.width * wm_h / wordmark.height)
    wm = wordmark.resize((wm_w, wm_h), Image.Resampling.LANCZOS)
    canvas.paste(wm, (72, 78), wm)

    draw = ImageDraw.Draw(canvas)
    bold = ImageFont.truetype(FONT_BOLD, 52)
    regular = ImageFont.truetype(FONT_REG, 26)
    draw.text((72, 280), "Photocatalytic oxidation", font=bold, fill=SLATE)
    draw.text((72, 352), "for air, and next, water.", font=bold, fill=BLUE_D)
    draw.rectangle((72, 450, 196, 456), fill=BLUE)
    draw.text(
        (72, 484),
        "Catalyx Technologies LLC  ·  FRESH+™ air systems  ·  Water treatment R&D",
        font=regular,
        fill=SLATE_2,
    )

    png = OUT / "catalyx-technologies-og.png"
    webp = OUT / "catalyx-technologies-og.webp"
    rgb = canvas.convert("RGB")
    rgb.save(png, "PNG", optimize=True)
    rgb.save(webp, "WEBP", quality=86, method=6)
    print(f"og: png={png.stat().st_size} webp={webp.stat().st_size}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    horizontal = Image.open(UPLOADS / "catalyx-horizontal_3f99.png").convert("RGBA")
    stacked = Image.open(UPLOADS / "catalyx-stacked_214b.png").convert("RGBA")

    wordmark = horizontal.crop(content_bbox(horizontal, pad=4))
    stacked_logo = stacked.crop(content_bbox(stacked, pad=8))
    # The wordmark sits inside the opening of the C, so a rectangular crop still
    # contains the start of "Catalyx". Keep only the molecule mesh.
    mark_region = horizontal.crop((0, 480, 620, 1160))
    mark = largest_component(mark_region)
    mark = mark.crop(content_bbox(mark, pad=2))

    # Header lockup is about 190px wide; 640px is roughly 3x. Footer stacked lockup
    # is about 200px wide; 480px is a bit over 2x. The molecule mark stays at its
    # cropped resolution for the hero watermark.
    save_logo(resized(wordmark, 640), "catalyx-technologies-wordmark")
    save_logo(resized(stacked_logo, 480), "catalyx-technologies-logo-stacked")
    save_logo(mark, "catalyx-technologies-mark")
    make_favicon(mark)
    make_og(wordmark, mark)


if __name__ == "__main__":
    main()
