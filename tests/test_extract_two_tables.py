"""The Dutch two-table lab layout: an overview table (lab ID -> our code) and results
tables keyed by the lab ID only. Every code, place and value here is invented."""
import os
import tempfile
import unittest

from reportlab.lib.pagesizes import A4
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from james.extract import extract_lab_text
from ai.james_ai.linker import parse_report

GRID = TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"), ("VALIGN", (0, 0), (-1, -1), "TOP")])


def make_two_table_pdf(path: str, replaces: bool = False) -> None:
    st = getSampleStyleSheet()["Normal"]
    parts = [Paragraph("Analyserapport: 99.0001/ T-ABC-1/ v2.0", st),
             Paragraph("Datum rapportage : 01 januari 2099", st),
             Paragraph("Uw referentie : Project 99-TEST | Demo bridge", st),
             Spacer(1, 12)]
    overview = [["ID", "Uw referentie", "Ontvangst\nMonstername", "Analysemethode(s)\nDatum analyse - analist"],
                ["T-ABC-1\n001", "HM-1\nLocatie: Demo railing. Kleur: groen", "01-01-2099\nOpdrachtgever",
                 "Visueel\nTEST-METHOD 1\n02-01-2099 - XX"],
                ["T-ABC-1\n002", "HM-2 Locatie Demo column paint", "01-01-2099\nOpdrachtgever",
                 "Visueel\nTEST-METHOD 1\n02-01-2099 - XX"],
                ["T-ABC-1\n003", "HM-3\nLocatie: Demo pillar", "01-01-2099\nOpdrachtgever",
                 "Visueel\nTEST-METHOD 1\n02-01-2099 - XX"]]
    parts.append(Table(overview, style=GRID))
    parts.append(PageBreak())
    res = [["ID", "Test/parameter", "Resultaat", "Eenheid"],
           ["T-ABC-1\n001", "Elementen\n- Lood (Pb)\n- Zink (Zn)", "123\n45,6", "mg/kg\nmg/kg"],
           # the lab writes the number without leading zeros here: still the same sample
           ["T-ABC-1 2", "Elementen\n- Lood (Pb)\n- Zink (Zn)", "<0,1\n<0,1", "mg/kg\nmg/kg"],
           # a lab ID that is not in the overview: must never be guessed
           ["T-ABC-1\n009", "Elementen\n- Lood (Pb)", "7", "mg/kg"]]
    parts.append(Table(res, style=GRID))
    if replaces:
        parts.append(Paragraph("(2) Dit document vervangt document 99.0001 / T-ABC-1 / v1.0, "
                               "document 99.0001 / T-ABC-1 / v1.0 is hiermee vervallen verklaard.", st))
    SimpleDocTemplate(path, pagesize=A4).build(parts)


def make_single_value_pdf(path: str) -> None:
    """A results table with the unit in the header and a remark letter, no parameter list."""
    st = getSampleStyleSheet()["Normal"]
    overview = [["ID", "Uw referentie", "Ontvangst\nMonstername", "Analysemethode"],
                ["Q-AAA-X", "CR6-1\nLocatie: Demo beam", "01-01-2099", "TEST-METHOD 2/Chroom-6\n02-01-2099 - XX"],
                ["Q-BBB-Y", "CR6-2\nLocatie: Demo fence", "01-01-2099", "TEST-METHOD 2/Chroom-6\n02-01-2099 - XX"]]
    res = [["ID", "Materiaal type", "Resultaat\n(mg/kg)", "Opm", "Q"],
           ["Q-AAA-X", "Demo paint", "<10", "C", "Q"],
           ["Q-BBB-Y", "Demo paint", "<10", "--", "Q"]]
    SimpleDocTemplate(path, pagesize=A4).build([Paragraph("Analyserapport: 99.0002/ Q-1/ v1.0", st),
                                                Table(overview, style=GRID), Spacer(1, 12),
                                                Table(res, style=GRID)])


class TwoTableLayout(unittest.TestCase):
    def read(self, maker, **kw):
        path = os.path.join(tempfile.mkdtemp(), "lab.pdf")
        maker(path, **kw)
        ex = extract_lab_text(path)
        return ex, *parse_report(ex.text)

    def test_our_code_comes_from_the_overview_and_results_are_joined_by_lab_id(self):
        ex, head, rows = self.read(make_two_table_pdf)
        self.assertEqual(head["project"], "99-TEST")
        self.assertEqual(head["report"], "99.0001/T-ABC-1/v2.0")
        got = {r.raw_id: r for r in rows}
        self.assertEqual(got["HM-1"].desc, "Demo railing. Kleur: groen")
        self.assertEqual(got["HM-1"].result, "Elementen: Lood (Pb) 123 mg/kg; Zink (Zn) 45,6 mg/kg")
        self.assertEqual(got["HM-1"].extra["method"], "Visueel, TEST-METHOD 1")
        self.assertEqual(got["HM-1"].extra["remarks"], "lab ID T-ABC-1 001")

    def test_lab_id_without_leading_zeros_still_joins(self):
        _, _, rows = self.read(make_two_table_pdf)
        hm2 = next(r for r in rows if r.raw_id == "HM-2")
        self.assertEqual(hm2.desc, "Demo column paint")
        self.assertEqual(hm2.result, "Elementen: all 2 parameters <0,1 mg/kg")

    def test_missing_result_and_unknown_lab_id_are_reported_not_guessed(self):
        ex, _, rows = self.read(make_two_table_pdf)
        hm3 = next(r for r in rows if r.raw_id == "HM-3")
        self.assertEqual(hm3.result, "")
        orphan = [r for r in rows if r.raw_id == "-"]
        self.assertEqual(len(orphan), 1)
        self.assertIn("7 mg/kg", orphan[0].result)
        self.assertTrue(any("No result found for HM-3" in n for n in ex.notes))
        self.assertTrue(any("not in the overview" in n for n in ex.notes))

    def test_a_replacing_report_says_so(self):
        ex, head, _ = self.read(make_two_table_pdf, replaces=True)
        self.assertEqual(head["replaces"], "99.0001/T-ABC-1/v1.0")
        self.assertTrue(any("replaces" in n for n in ex.notes))

    def test_unit_from_header_and_remark_letter_are_kept(self):
        ex, _, rows = self.read(make_single_value_pdf)
        got = {r.raw_id: r.result for r in rows}
        self.assertEqual(got["CR6-1"], "<10 mg/kg (lab remark C)")
        self.assertEqual(got["CR6-2"], "<10 mg/kg")
        self.assertTrue(any("remark C" in n for n in ex.notes))


class Dev4AsPdf(unittest.TestCase):
    """The dev4 PDF for the app must read back as exactly the dev4 lines, so a test in the
    app and a scored run see the same input."""

    def test_extractor_reads_back_every_dev4_line(self):
        from ai.james_ai.make_lab_pdf import make_lab_pdf
        from ai.james_ai.score import load_cases
        lines = [c["line"] for c in load_cases()["cases"] if c["set"] == "dev4"]
        path = os.path.join(tempfile.mkdtemp(), "dev4.pdf")
        make_lab_pdf(path, lines, "DEV-4", "TEST/DEV4/v1.0")
        ex = extract_lab_text(path)
        head, rows = parse_report(ex.text)
        self.assertEqual(head["project"], "DEV-4")
        want = [[p.strip() for p in ln.split("|", 2)] for ln in lines]
        self.assertEqual([[r.raw_id, r.desc, r.result] for r in rows], want)


if __name__ == "__main__":
    unittest.main()
