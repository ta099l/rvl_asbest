"""Photos: check, store, number and propose a link. Fictitious demo photos only until RVL approves real ones.

Everything about a photo file lives here, so the server only moves bytes and calls these functions:
- check_image():   magic bytes first (JPEG FF D8 FF, PNG 89 50 4E 47), so a renamed text file never reaches Pillow;
- process():       open with Pillow, turn upright from the EXIF orientation, save a NEW JPEG plus a 400 px
                   thumbnail. Re-encoding drops all EXIF data, including GPS positions from phones;
- store_files():   write both files under <data>/photos/<object id>/, named by the sha256 of the upload;
- next_photo_no(): the next number in the project's own format (F-013 after F-012; 1, 2, 3 when none yet);
- propose():       a sample or source code in the file name -> proposed link, using the linker's code reader.
"""
import hashlib
import io
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"
THUMB_PX = 400
MAX_PIXELS = 60_000_000            # a "decompression bomb" (a tiny file that unpacks to a huge image) is refused
STORED_NAME = re.compile(r"^[0-9a-f]{64}$")


class PhotoError(ValueError):
    """A photo the inspector has to fix (wrong type, broken file); the message says what to do."""


def max_photo_bytes() -> int:
    return int(float(os.environ.get("JAMES_MAX_PHOTO_MB") or 15) * 1024 * 1024)


def data_dir(db_path: str) -> Path:
    """JAMES_DATA_DIR, else the folder of the database file, else ./data (database in memory)."""
    env = os.environ.get("JAMES_DATA_DIR")
    if env:
        return Path(env)
    if db_path and db_path != ":memory:":
        return Path(db_path).resolve().parent
    return ROOT / "data"


def check_image(data: bytes) -> str:
    """'jpeg' or 'png' from the first bytes; anything else is refused before Pillow sees it."""
    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if data.startswith(PNG_MAGIC):
        return "png"
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        raise PhotoError("this is a HEIC photo (iPhone): please export it as JPG and upload again")
    raise PhotoError("not a JPG or PNG photo: please export it as JPG and upload again")


def process(data: bytes) -> Tuple[bytes, bytes, int, int]:
    """(jpeg, thumbnail jpeg, width, height): upright, re-encoded, without EXIF."""
    from PIL import Image, ImageOps
    kind = check_image(data)
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format.lower() != kind:
                raise PhotoError("the file content does not match a JPG or PNG photo: please export it as JPG")
            im.load()
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, "white")
                bg.paste(im, mask=im.getchannel("A"))
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
            full = io.BytesIO()
            im.save(full, "JPEG", quality=88, optimize=True)        # a new file: no EXIF, so no GPS
            th = im.copy()
            th.thumbnail((THUMB_PX, THUMB_PX))
            thumb = io.BytesIO()
            th.save(thumb, "JPEG", quality=80)
            return full.getvalue(), thumb.getvalue(), im.width, im.height
    except PhotoError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PhotoError("this image is far too large in pixels to be a site photo")
    except Exception as e:                       # truncated or broken file: the inspector exports it again
        raise PhotoError(f"the photo could not be read ({type(e).__name__}): please export it as JPG again")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def photo_path(base: Path, object_id: int, stored_name: str, thumb: bool = False) -> Path:
    """The only way a file path is made: from the generated stored name, never from user input."""
    if not STORED_NAME.match(stored_name or ""):
        raise ValueError("not a stored photo name")
    folder = base / "photos" / str(int(object_id))
    return (folder / "thumbs" if thumb else folder) / f"{stored_name}.jpg"


def store_files(base: Path, object_id: int, stored_name: str, full: bytes, thumb: bytes) -> None:
    """Write photo and thumbnail; a half-written file never appears under its final name."""
    for path, data in ((photo_path(base, object_id, stored_name), full),
                       (photo_path(base, object_id, stored_name, thumb=True), thumb)):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)


# ---------- numbering: the project's own format, in one place ----------
NUMBERED = re.compile(r"^(.*?)(\d+)$")


def next_photo_no(existing: Iterable[str]) -> str:
    """The next photo number in the format the project already uses: F-013 after F-012, 8 after 7."""
    return next_number(existing, first="1")


def next_number(existing: Iterable[str], first: str = "1") -> str:
    """The next number in the format a project already uses: F-013 after F-012, B11 after B10, 8 after 7.
    One place for this rule, for photo numbers and source numbers. Nothing numbered yet: `first`."""
    best = None
    for no in existing:
        m = NUMBERED.match((no or "").strip())
        if m and (best is None or int(m.group(2)) > best[1]):
            best = (m.group(1), int(m.group(2)), m.group(2))
    if best is None:
        return first
    head, n, digits = best
    width = len(digits) if digits.startswith("0") and len(digits) > 1 else 1
    return head + str(n + 1).zfill(width)


# ---------- the proposed link, from the file name ----------
# A code in a file name: CR6/CH6 first (their prefix ends in a digit), then letters + optional - or space +
# number. "hm12_2.jpg" -> HM12; "MM-1 F-012 pipe.jpg" -> MM-1 and F-012; "B4 overview.jpg" -> B4.
NAME_CODE = re.compile(r"(?<![A-Z0-9])(CR6|CH6|[A-Z]+)[ -]?(\d+)(?![0-9])")


def name_keys(filename: str) -> List[str]:
    """Every code in a file name as the linker's alias key ('HM|12'), in order, without duplicates."""
    from ai.james_ai.linker import alias_key
    stem = Path(filename or "").stem.upper().replace("_", " ")
    out = []
    for m in NAME_CODE.finditer(stem):
        key = alias_key(m.group(1) + "-" + m.group(2))
        if key and key not in out:
            out.append(key)
    return out


def propose(filename: str, samples: Dict[str, str], sources: Iterable[str]) -> Tuple[Optional[str], Optional[str], str]:
    """(sample code, source number, reason) for a file name. samples: code -> its source number.

    Rules only, no AI, the same code reader as the linker (MM-1, M01, mm 1 and M-1 are the same sample).
    One sample in the name wins; else one source; two different ones -> no proposal, with the reason.
    """
    from ai.james_ai.linker import alias_key
    keys = name_keys(filename)
    by_key = {alias_key(c): c for c in samples}
    hit_samples = [by_key[k] for k in keys if k in by_key]
    src_key = {alias_key(s): s for s in sources}
    hit_sources = [src_key[k] for k in keys if k in src_key]
    if len(set(hit_samples)) > 1:
        return None, None, f"the file name names more than one sample ({', '.join(hit_samples)}): choose one"
    if hit_samples:
        code = hit_samples[0]
        return code, samples.get(code) or None, f"sample code {code} in the file name"
    if len(set(hit_sources)) > 1:
        return None, None, f"the file name names more than one source ({', '.join(hit_sources)}): choose one"
    if hit_sources:
        return None, hit_sources[0], f"source {hit_sources[0]} in the file name"
    return None, None, "no sample or source code in the file name"


def matches_photo_no(filename: str, photo_no: str) -> bool:
    """True when the file name carries this photo number (F-012 in 'MM-1 F-012 pipe.jpg', also F012 or f-12)."""
    from ai.james_ai.linker import alias_key
    key = alias_key(photo_no or "")
    return bool(key) and key in name_keys(filename)
