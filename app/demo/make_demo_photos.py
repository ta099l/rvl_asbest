"""Make fictional demo photos for the demo ship MV Noorderlicht, to show automatic photo linking.

    .venv/bin/python app/demo/make_demo_photos.py [output folder]     (default: data/demo_photos)

Each image is a plain colour with a caption such as "Foto 7 - MM-3 gasket flange (fictional)". The file
names start with the sample code (or a source code), so James can propose the link:
- 8 carry the photo number that is already registered for that sample (MM-1 F-012 ...): they fill that row;
- 9 carry only a sample or source code (M02_2, ods1, B10, ...): new numbers with a proposed link;
  MM-1 gets five photos, so the link check shows "more than 4 photos" for source B01;
- 2 cannot be linked: an overview without a code, and a typo (MI02 for M02).
One photo is a PNG, one has an EXIF "rotate" tag (it must come out upright). Everything is made up.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
PHOTOS = [
    ("MM-1 F-012 exhaust pipe insulation.jpg", "#b7c4cf"), ("MM-2 F-018 floor tile cabin.jpg", "#d9c9a7"),
    ("MM-3 F-024 gasket flange.jpg", "#7d8a7a"), ("MM-4 F-031 bulkhead board.jpg", "#c9c2b8"),
    ("PBS-1 F-040 cable bundle.jpg", "#4d4d4d"), ("OS-1 F-044 transformer.jpg", "#a8742f"),
    ("HM-1 F-051 railing paint.jpg", "#a33d32"), ("PBS-2 F-057 window rubber.jpg", "#2f3a45"),
    ("MM-1_2 exhaust pipe detail.jpg", "#aab8c2"), ("MM-1_3 exhaust pipe label.jpg", "#9fb0bc"),
    ("MM-1_4 exhaust pipe bend.jpg", "#94a6b4"), ("MM-1_5 exhaust pipe end.jpg", "#899dab"),
    ("M02_2 floor tile close-up.jpg", "#e3d5b6"), ("ods1 cold room foam.jpg", "#e8d66a"),
    ("pbs 1 cable label.png", "#5c5c5c"), ("HM-1_2 railing paint layers.jpg", "#8f362c"),
    ("B10 welded panel no access.jpg", "#6b6f73"), ("overview engine room.jpg", "#56636b"),
    ("MI02 cabin tile.jpg", "#cbbd9d"),
]
ROTATED = "MM-3 F-024 gasket flange.jpg"      # stored sideways with EXIF orientation 6: James turns it upright


def make(folder: Path) -> list:
    folder.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=56)
    small = ImageFont.load_default(size=32)
    out = []
    for n, (name, colour) in enumerate(PHOTOS, start=1):
        im = Image.new("RGB", (1600, 1200), colour)
        d = ImageDraw.Draw(im)
        label = Path(name).stem.replace("_", " ")
        d.text((80, 480), f"Foto {n} - {label} (fictional)", fill="white", font=font, stroke_width=3, stroke_fill="black")
        d.text((80, 580), "MV Noorderlicht demo · James", fill="white", font=small, stroke_width=2, stroke_fill="black")
        path = folder / name
        if name == ROTATED:
            exif = Image.Exif()
            exif[0x0112] = 6                      # "rotate 90° clockwise to view": a phone held upright
            im.rotate(90, expand=True).save(path, "JPEG", quality=85, exif=exif)
        elif name.endswith(".png"):
            im.save(path, "PNG")
        else:
            im.save(path, "JPEG", quality=85)
        out.append(path)
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "demo_photos"
    files = make(target)
    print(f"{len(files)} fictional demo photos in {target}")
