"""Build test lab-report PDFs from the demo report text."""
import glob
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_text_pdf(path: str, text: str) -> None:
    head, _, rest = text.partition("\n---\n")
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    c.setFont("Helvetica", 12)
    for ln in head.split("\n"):
        c.drawString(50, y, ln)
        y -= 20
    y -= 15
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "ID")
    c.drawString(120, y, "Description")
    c.drawString(390, y, "Result")
    y -= 22
    c.setFont("Helvetica", 12)
    for ln in rest.split("\n"):
        idc, desc, res = [p.strip() for p in ln.split("|", 2)]
        c.drawString(50, y, idc)
        c.drawString(120, y, desc)
        c.drawString(390, y, res)
        y -= 20
    c.save()


def make_scan_pdf(path: str, text: str, blur: float = 0.8, rotate: float = 0.5) -> None:
    """Render the text PDF to an image, soften and tilt it a little, save as image-only PDF."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.pdf")
        make_text_pdf(src, text)
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", src, os.path.join(tmp, "p")],
                       check=True, capture_output=True)
        img = Image.open(os.path.join(tmp, "p.png")).convert("L")
        img = img.rotate(rotate, expand=False, fillcolor=255).filter(ImageFilter.GaussianBlur(blur))
        img.save(path, "PDF", resolution=150)
