"""One bronblad per source in the .odt, with real photos (fictional data and a fixture template only).

RVL's real template is not used: the fixture in test_export.py has the same structure (a source block per
2.3.x section, and a 2 x 4 photo grid of image rows and "Foto | <samplenumber>" caption rows).
"""
import io
import os
import re
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from PIL import Image

from app.export_odt import (EMPTY_SECTION, NS, fill_photo_grid, export, manifest_with_pictures, photo_cell_widths,
                            photo_frame, photo_size)
from app.server import Service
from app.test_export import CONTENT, PHOTO_GRID, make_template

BY = "Test Inspector (fictitious)"
SHA = "a" * 64
WRAP = ('<root xmlns:draw="{draw}" xmlns:xlink="{xlink}" xmlns:svg="{svg}" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0">{{}}</root>').format(**NS)


def jpeg(colour, size=(64, 48)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", size, colour).save(b, "JPEG")
    return b.getvalue()


class FrameHelper(unittest.TestCase):
    def test_frame_is_valid_xml_with_the_photo_in_pictures(self):
        x = photo_frame(SHA, 1600, 1200, 7.7, 'Foto F-012 "1"')
        root = ET.fromstring(WRAP.format(x))
        frame = root[0]
        img = frame[0]
        self.assertEqual(img.get(f"{{{NS['xlink']}}}href"), f"Pictures/{SHA}.jpg")
        self.assertEqual((frame.get(f"{{{NS['svg']}}}width"), frame.get(f"{{{NS['svg']}}}height")), ("7.7cm", "5.775cm"))

    def test_size_keeps_the_aspect_ratio_and_the_maximum_height(self):
        self.assertEqual(photo_size(1600, 1200, 7.7), (7.7, 5.775))      # landscape: full cell width
        w, h = photo_size(1200, 1600, 7.7)                               # portrait: 6 cm high at most
        self.assertEqual(h, 6.0)
        self.assertAlmostEqual(w / h, 1200 / 1600, places=3)

    def test_only_a_stored_name_can_become_a_path(self):
        with self.assertRaises(ValueError):
            photo_frame("../../etc/passwd", 10, 10, 5, "x")

    def test_caption_is_escaped(self):
        p = {"photo_no": "F-1", "sample": "MM-1", "description": "Pipe & <flange> \"A\"", "file": True,
             "sha": SHA, "width": 400, "height": 300, "path": "x"}
        out = fill_photo_grid(PHOTO_GRID, [p], [7.7, 8.0], {})
        ET.fromstring(WRAP.format(out))                                  # still well-formed
        self.assertIn("Foto | F-1 · MM-1 – Pipe &amp; &#60;flange&gt;", out)            # '<' as &#60;: never a placeholder

    def test_column_width_minus_padding_from_the_template_styles(self):
        widths = photo_cell_widths(CONTENT, PHOTO_GRID)
        self.assertEqual([round(w, 2) for w in widths], [7.70, 8.01])    # 3.15in and 3.27in minus 2 x 0.059in
        self.assertEqual(photo_cell_widths("", PHOTO_GRID.replace("f.A", "x.A").replace("f.B", "x.B")), [7.5, 7.5])

    def test_manifest_lists_each_picture_once(self):
        m = manifest_with_pictures(None, [SHA, SHA, "b" * 64])
        ET.fromstring(m)
        self.assertEqual(m.count(f"Pictures/{SHA}.jpg"), 1)


class GridFill(unittest.TestCase):
    def photos(self, n, file=True):
        return [{"photo_no": f"F-{k}", "sample": "MM-2", "description": f"tile {k}", "file": file,
                 "sha": f"{k:064x}", "width": 400, "height": 300, "path": f"/x/{k}"} for k in range(1, n + 1)]

    def test_five_photos_add_a_pair_of_rows_and_drop_none(self):
        pics = {}
        out = fill_photo_grid(PHOTO_GRID, self.photos(5), [7.7, 8.0], pics)
        self.assertEqual(out.count("<table:table-row>"), 6)             # 3 pairs of image + caption rows
        self.assertEqual(out.count("<draw:frame"), 5)
        self.assertEqual(len(pics), 5)
        self.assertEqual(out.count("Foto | "), 5)                       # the unused 6th cell stays empty
        self.assertNotIn("&lt;samplenumber&gt;", out)
        self.assertNotIn("Foto | –", out)

    def test_photo_without_file_says_photo_missing(self):
        out = fill_photo_grid(PHOTO_GRID, self.photos(1, file=False), [7.7, 8.0], {})
        self.assertIn("Foto | F-1 · MM-2 – photo missing", out)
        self.assertNotIn("<draw:frame", out)


class DemoExport(unittest.TestCase):
    """The demo ship with every line approved and photos uploaded, exported into the fixture template."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.s = Service(":memory:", data_dir=self.dir)
        self.oid = self.s.demo_object
        self.rid = self.s.view(None, self.oid)["report"]["id"]
        for x in self.s.view(self.rid, self.oid)["report"]["rows"]:
            self.s.decide(self.rid, x["idx"], "approve" if x["proposal"]["sample"] else "reject", BY, None, "")
        self.s.upload_photo(self.oid, "MM-1 F-012 pipe.jpg", jpeg("navy"), BY)
        for k in range(5):                                              # MM-2: its own F-018 (no file) + 5 uploads
            self.s.upload_photo(self.oid, f"MM-2_{k} tile.jpg", jpeg((k * 40, 90, 60), size=(60, 80) if k == 0 else (64, 48)), BY)
        self.s.accept_photo_proposals(self.oid, BY)
        self.tpl = Path(tempfile.mkdtemp()) / "template.odt"
        make_template(self.tpl)

    def odt(self):
        return export(self.s.view(self.rid, self.oid)["report"], self.tpl)

    def test_zip_is_valid_and_pictures_match_the_manifest(self):
        data = self.odt()
        z = zipfile.ZipFile(io.BytesIO(data))
        first = z.infolist()[0]
        self.assertEqual((first.filename, first.compress_type), ("mimetype", zipfile.ZIP_STORED))
        content = z.read("content.xml").decode()
        ET.fromstring(content)
        manifest = z.read("META-INF/manifest.xml").decode()
        ET.fromstring(manifest)
        pictures = {n for n in z.namelist() if n.startswith("Pictures/")}
        in_manifest = set(re.findall(r'manifest:full-path="(Pictures/[^"]+)"', manifest))
        self.assertEqual(pictures, in_manifest)
        self.assertEqual(pictures, set(re.findall(r'xlink:href="(Pictures/[^"]+)"', content)))
        self.assertEqual(len(pictures), 6)                              # MM-1's photo and MM-2's five uploads
        for n in pictures:
            Image.open(io.BytesIO(z.read(n))).verify()

    def test_same_data_same_bytes(self):
        self.assertEqual(self.odt(), self.odt())

    def blocks(self, content):
        """Text of each source block, keyed by source number."""
        parts = re.split(r"<text:p >Source (B\d+) – Source Record</text:p>", content)
        return {parts[i]: parts[i + 1].split("<text:h")[0] for i in range(1, len(parts), 2)}

    def test_every_source_once_with_only_its_own_lab_rows_and_photos(self):
        content = zipfile.ZipFile(io.BytesIO(self.odt())).read("content.xml").decode()
        blocks = self.blocks(content)
        self.assertEqual(sorted(blocks), ["B01", "B02", "B03", "B05", "B06", "B07", "B08", "B09"])
        self.assertEqual(content.count("– Source Record</text:p>"), 8)
        b02 = blocks["B02"]
        lab = re.search(r'<table:table table:name="l">.*?</table:table>', b02).group(0)
        self.assertEqual(re.findall(r"<text:p>(MM-\d+)</text:p>", lab), ["MM-2"])   # only its own sample
        self.assertNotIn(">MM-1<", b02)
        self.assertEqual(b02.count("<draw:frame"), 5)                   # all five, none dropped
        self.assertIn("F-018 · MM-2 – photo missing", b02)              # the registered number without a file
        self.assertEqual(blocks["B01"].count("<draw:frame"), 1)
        self.assertIn("Condition", b02)

    def test_a_section_without_sources_keeps_one_line(self):
        content = zipfile.ZipFile(io.BytesIO(self.odt())).read("content.xml").decode()
        pfos = content.split(">2.3.4</text:h>")[1].split(">2.3.5</text:h>")[0]
        self.assertIn(f"<text:p >{EMPTY_SECTION}</text:p>", pfos)
        self.assertNotIn("Source Record", pfos)
        self.assertNotIn("<table:table table:name=\"f\"", pfos)          # no empty photo grid either
        self.assertEqual(pfos.count('<table:table table:name="s">'), 1)  # the overview table stays, once

    def test_fixed_text_stays_exactly_as_in_the_template(self):
        content = zipfile.ZipFile(io.BytesIO(self.odt())).read("content.xml").decode()
        text = lambda xml: [re.sub(r"<[^>]+>", "", m) for m in re.findall(r"<text:[ph][ >].*?</text:[ph]>", xml)]
        # the variable part is the source block (copied per source, or one line when empty): leave it out
        outside = re.sub(r'<text:p >Source&lt;source_number&gt;.*?<table:table table:name="f">.*?</table:table>', "",
                         CONTENT, flags=re.S)
        fixed = [t for t in text(outside) if "&lt;" not in t]
        out = text(content)
        pos = 0
        for t in fixed:                                                 # every fixed paragraph, in the same order
            pos = out.index(t, pos) + 1 if t in out[pos:] else self.fail(f"fixed text changed or lost: {t!r}")
        self.assertEqual(sum(t.startswith("Foto | ") for t in out), content.count("Foto | "))

    def test_signed_but_with_link_errors_is_still_a_draft(self):
        self.s.sign(self.rid, BY)
        self.assertTrue([i for i in self.s.link_check(self.oid) if i["severity"] == "error"])
        with mock.patch.dict(os.environ, {"JAMES_IHM_TEMPLATE": str(self.tpl)}):
            data, name = self.s.export(self.rid)
        self.assertTrue(name.endswith("_DRAFT.odt"))
        content = zipfile.ZipFile(io.BytesIO(data)).read("content.xml").decode()
        self.assertNotIn(">Final<", content)


if __name__ == "__main__":
    unittest.main()
