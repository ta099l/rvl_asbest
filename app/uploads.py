"""The upload page: sort every dropped file, and store the ones that are documents (drawings).

sort_file() decides from the first bytes and the file name, never from the name alone:
- a PDF                                  -> "pdf"     (the server then looks for a lab results table);
- a JPG or PNG whose name says drawing   -> "drawing" (GA-02 ..., ... deck plan.png, Layout ...);
- any other JPG, PNG or HEIC              -> "photo"   (the P4 photo flow; HEIC gets "export as JPG" there);
- anything else                           -> refused.
A PDF whose name says drawing is filed as a drawing without reading it.
"""
import os
import re
from pathlib import Path
from typing import Tuple

from app.photos import JPEG_MAGIC, PNG_MAGIC, STORED_NAME

PDF_MAGIC = b"%PDF"
# Whole words only: "plan" yes, "plank" or "floorplanner" no. "GA" only at the very start, followed by -, _ or space.
DRAWING_WORDS = re.compile(r"(?<![A-Za-z0-9])(drawings?|tekening(?:en)?|plans?|layouts?)(?![A-Za-z0-9])", re.I)
GA_START = re.compile(r"^GA[-_ ]", re.I)
DOC_EXT = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}


def max_pdf_bytes() -> int:
    """PDFs come as raw bytes here (not base64 in JSON), so the old 20 MB limit applies."""
    return int(float(os.environ.get("JAMES_MAX_PDF_MB") or 20) * 1024 * 1024)


def looks_like_drawing(name: str) -> bool:
    stem = Path(name or "").stem
    return bool(GA_START.match(stem) or DRAWING_WORDS.search(stem.replace("_", " ")))


def sort_file(name: str, data: bytes) -> str:
    """'pdf', 'drawing', 'photo' or 'unknown'."""
    image = data.startswith(JPEG_MAGIC) or data.startswith(PNG_MAGIC) or data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1")
    if data.startswith(PDF_MAGIC):
        return "drawing" if looks_like_drawing(name) else "pdf"
    if image:
        return "drawing" if looks_like_drawing(name) and not data[4:12].startswith(b"ftyp") else "photo"
    return "unknown"


def mime_of(data: bytes) -> str:
    if data.startswith(PDF_MAGIC):
        return "application/pdf"
    if data.startswith(PNG_MAGIC):
        return "image/png"
    if data.startswith(JPEG_MAGIC):
        return "image/jpeg"
    raise ValueError("not a PDF, PNG or JPG file")


def document_path(base: Path, object_id: int, stored_name: str) -> Path:
    """The only way a document path is made: <data>/docs/<object>/<sha256>.<ext>, from the generated name."""
    stem, _, ext = (stored_name or "").partition(".")
    if not STORED_NAME.match(stem) or "." + ext not in DOC_EXT.values():
        raise ValueError("not a stored document name")
    return base / "docs" / str(int(object_id)) / stored_name


def store_document(base: Path, object_id: int, sha: str, data: bytes) -> Tuple[str, str]:
    """Write the file as received (a drawing is not re-encoded); returns (stored name, mime)."""
    mime = mime_of(data)
    name = sha + DOC_EXT[mime]
    path = document_path(base, object_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return name, mime
