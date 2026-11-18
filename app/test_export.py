"""Tests for filling the IHM template (fictional data only).

RVL's real template is not in the repository, so these tests build a small
template with the same patterns: placeholders in table rows, a Source Record
heading plus table, a lab table, a photo grid and the fixed lines of Table 15.
One extra test uses the real template when it is present on this computer.
"""
import io
import re
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from app.export_odt import export, template_path
from app.server import Service

NS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
      'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
      'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
      'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
      'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"')
MANIFEST = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" '
            'manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>'
            '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>')


def cell(t):
    return f'<table:table-cell><text:p>{t}</text:p></table:table-cell>'


def row(*cells):
    return "<table:table-row>" + "".join(cell(c) for c in cells) + "</table:table-row>"


def table(name, *rows):
    return f'<table:table table:name="{name}">' + "".join(rows) + "</table:table>"


def ph(n):
    return f"&lt;{n}&gt;"


def section(title, sample_tag="sampleno"):
    return (f"<text:h text:outline-level=\"3\">{title}</text:h>"
            + table("s", row("Sample No.", "Deck Level"), row(ph(sample_tag), ph("decklevel" if sample_tag == "sampleno" else "deck_level")))
            + f"<text:p >Source{ph('source_number')}– Source Record</text:p>"
            + table("r", row("Description", "Details"), row("Source Description", ph("source_description")),
                    row("Quantity", ph("quantity")), row("Conclusions and/or Recommendations", "This concerns"))
            + table("l", row("Sample Number", "Certificate Number"), row(ph("samplenumber"), ph("certificatenumber")))
            + PHOTO_GRID)


# The photo grid as in RVL's template: 2 columns x 4 rows, in pairs of an image row (an empty paragraph per
# cell) and a caption row ("Foto | <samplenumber>"). Column widths and cell padding come from automatic styles.
_IMG = '<table:table-cell table:style-name="f.A1"><text:p text:style-name="P1"/></table:table-cell>'
_CAP = '<table:table-cell table:style-name="f.A1"><text:p text:style-name="P2">Foto | &lt;samplenumber&gt;</text:p></table:table-cell>'
PHOTO_GRID = ('<table:table table:name="f"><table:table-column table:style-name="f.A"/><table:table-column table:style-name="f.B"/>'
              + ("<table:table-row>" + _IMG * 2 + "</table:table-row><table:table-row>" + _CAP * 2 + "</table:table-row>") * 2
              + "</table:table>")
AUTOMATIC_STYLES = ('<office:automatic-styles>'
                    '<style:style style:name="f.A" style:family="table-column"><style:table-column-properties style:column-width="3.15in"/></style:style>'
                    '<style:style style:name="f.B" style:family="table-column"><style:table-column-properties style:column-width="3.27in"/></style:style>'
                    '<style:style style:name="f.A1" style:family="table-cell"><style:table-cell-properties fo:padding="0.059in"/></style:style>'
                    '</office:automatic-styles>')


CONTENT = (f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {NS}>{AUTOMATIC_STYLES}<office:body><office:text>'
           + table("p", row("Project Number", ph("projectnumber")), row("Report Status", ph("reportstatus")))
           + table("i1", row("No.", "Application of Paint", "Name of Paints"), row(ph("no"), ph("application"), ph("paintname")))
           + table("i2", row("No.", "Name of Equipment"), row(ph("no"), ph("equipment")))
           + table("i3", row("No.", "Structural Component"), row(ph("no"), ph("component")))
           + "".join(section(f"2.3.{n}", "sampleno" if n == 1 else "sample_number") for n in range(1, 8))
           + table("lim", row("No.", "Restriction"), row(ph("restriction_number"), ph("restriction_reason")))
           + table("t15", row("Hazardous Material", "Quantity", "Unit", "IHM Table"),
                   row("A-1 Asbestos", ph("quantity"), ph("unit"), "A"), row("A-2 Polychlorinated Biphenyls (PCB)", ph("quantity"), ph("unit"), "A"))
           + f"<text:p>Survey Findings:{ph('surveyfindings')}</text:p>"
           + "</office:text></office:body></office:document-content>")


def make_template(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.text", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", CONTENT)
        z.writestr("META-INF/manifest.xml", MANIFEST)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        r = self.s.view(None)["report"]
        self.rid = r["id"]
        for x in r["rows"]:
            self.s.decide(self.rid, x["idx"], "approve" if x["proposal"]["sample"] else "reject", "A. Surveyor", None, "")
        self.tpl = Path(tempfile.mkdtemp()) / "template.odt"
        make_template(self.tpl)

    def content(self, data: bytes) -> str:
        z = zipfile.ZipFile(io.BytesIO(data))
        self.assertEqual(z.infolist()[0].filename, "mimetype")
        x = z.read("content.xml").decode("utf-8")
        ET.fromstring(x)                                   # still well-formed
        return x

    def test_every_placeholder_is_filled(self):
        x = self.content(export(self.s.view(self.rid)["report"], self.tpl))
        self.assertEqual(re.findall(r"&lt;[a-z_]+&gt;", x), [])
        self.assertIn(">J-26-014<", x)
        self.assertIn(">Draft<", x)

    def test_rows_and_source_records_are_repeated_per_item(self):
        x = self.content(export(self.s.view(self.rid)["report"], self.tpl))
        self.assertIn("Paint layer (3 coats) (HM-1)", x)                     # I-1
        self.assertEqual(x.count("Source B0"), 8)                           # 8 approved lines; MM-9 was rejected
        self.assertIn("This concerns Asbestos", x)
        self.assertIn(">C-4471-02<", x)

    def test_source_table_only_adds_the_condition_line(self):
        """The bronblad reads the source table first. For the demo ship that gives the same report as the
        old sample-based values, except one new Condition row per Source Record."""
        new = self.content(export(self.s.view(self.rid)["report"], self.tpl))
        self.s.store.db.execute("DELETE FROM source")          # back to the old, sample-based values
        old = self.content(export(self.s.view(self.rid)["report"], self.tpl))
        cond = re.compile(r"<table:table-row><table:table-cell><text:p>Condition</text:p></table:table-cell>.*?</table:table-row>")
        # one per bronblad: the 8 demo sources with an approved line (empty sections have no Source Record now)
        self.assertEqual(len(cond.findall(new)), 8)
        self.assertIn("<text:p>Damaged</text:p>", new)           # B01, the exhaust pipe insulation
        self.assertEqual(cond.sub("", new), cond.sub("", old))   # everything else is the same

    def test_fixed_lines_get_quantities_from_the_registration(self):
        x = self.content(export(self.s.view(self.rid)["report"], self.tpl))
        a1 = re.search(r"A-1 Asbestos.*?</table:table-row>", x).group(0)
        a2 = re.search(r"A-2 Polychlorinated.*?</table:table-row>", x).group(0)
        self.assertIn("to be filled in", a1)                               # m and pcs do not add up
        self.assertIn(">35<", a2)
        self.assertIn(">kg<", a2)

    def test_signed_report_says_final(self):
        self.s.sign(self.rid, "B. Reviewer")
        self.assertIn(">Final<", self.content(export(self.s.view(self.rid)["report"], self.tpl)))

    def test_missing_template_gives_a_clear_error(self):
        with self.assertRaises(FileNotFoundError) as e:
            export(self.s.view(self.rid)["report"], Path(tempfile.mkdtemp()) / "nope.odt")
        self.assertIn("JAMES_IHM_TEMPLATE", str(e.exception))

    def test_practice_report_cannot_be_exported(self):
        rid = self.s.load_practice()
        with self.assertRaises(ValueError):
            self.s.export(rid)

    @unittest.skipUnless(template_path().is_file(), "RVL's IHM template is not on this computer")
    def test_real_template(self):
        data, name = self.s.export(self.rid)
        x = self.content(data)
        self.assertEqual(re.findall(r"&lt;[a-z_]+&gt;", x), [])
        self.assertTrue(name.endswith("_DRAFT.odt"))
        self.assertIn("B3 Lead (100 mg/kg) – Paint", re.sub(r"<[^>]+>", "", x))


if __name__ == "__main__":
    unittest.main()
