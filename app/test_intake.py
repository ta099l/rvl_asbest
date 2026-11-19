"""Intake, vessel reuse, desk research rows and their place in the export (fictional data, fixture template)."""
import io
import re
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from app import export_odt
from app.server import Service
from app.test_export import make_template

BY = "Test Inspector (fictitious)"
NEW = {"name": "MV Intake Test (fictitious)", "project": "J-26-610", "ref": "IMO 9100001", "kind": "Bulk carrier",
       "flag": "NL", "year_built": "2004", "yard": "Example Yard (fictitious)", "owner": "Owner B.V. (fictitious)",
       "operator": "Operator Ltd. (fictitious)", "client": "Client B.V. (fictitious)", "survey_type": "IHM Part I",
       "loc_port": "Rotterdam", "loc_country": "NL", "loc_quay": "Quay 4 (fictitious)", "loc_yard": "Yard X (fictitious)"}


class Intake(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:", data_dir=tempfile.mkdtemp())

    def test_new_project_from_intake_alone(self):
        oid = self.s.new_project(NEW)
        o = self.s.view(None, oid)["object"]
        self.assertEqual(o["site"], "Quay 4 (fictitious), Yard X (fictitious), Rotterdam, NL")   # made from the parts
        self.assertEqual((o["info"]["flag"], o["info"]["year_built"], o["info"]["survey_type"]), ("NL", "2004", "IHM Part I"))
        with self.assertRaisesRegex(ValueError, "survey location"):
            self.s.new_project({"name": "MV X", "project": "J-1"})                             # no port, no country

    def test_changing_a_location_part_changes_the_survey_location_and_is_logged(self):
        oid = self.s.new_project(NEW)
        self.s.update_project({"loc_quay": "Quay 7 (fictitious)", "operator": "Other Ltd."}, BY, oid)
        o = self.s.view(None, oid)["object"]
        self.assertTrue(o["site"].startswith("Quay 7 (fictitious), "))
        self.assertIn("operator:", self.s.store.register_log(oid)[-1]["detail"])

    def test_an_older_project_keeps_working_without_the_new_fields(self):
        o = self.s.view(None, self.s.demo_object)["object"]
        self.assertEqual((o["info"]["flag"], o["info"]["loc_port"]), ("", ""))
        self.assertEqual(o["site"], "Shipyard, Rotterdam")

    def test_same_imo_number_offers_the_earlier_vessel(self):
        first = self.s.new_project(NEW)
        second = self.s.new_project({**{k: "" for k in NEW}, "name": "x", "project": "J-26-611", "ref": "9100001", "loc_port": "Antwerp"})
        vessels = {v["id"]: v for v in self.s.view(None, second)["vessels"]}
        self.assertEqual((vessels[first]["imo"], vessels[second]["imo"]), ("9100001", "9100001"))   # digits only
        self.assertEqual((vessels[first]["flag"], vessels[first]["operator"]), ("NL", "Operator Ltd. (fictitious)"))


class DeskResearch(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:", data_dir=tempfile.mkdtemp())
        self.oid = self.s.demo_object

    def test_consultation_rows_add_change_remove_and_log(self):
        rid = self.s.save_table_row("consultation", self.oid, {"consultation": "Interview on board", "name_rank": "J. Example, Chief Engineer"}, BY)
        self.s.save_table_row("consultation", self.oid, {"id": rid, "result": "No asbestos work since 2010 (fictitious)"}, BY)
        rows = self.s.view(None, self.oid)["consultation"]
        self.assertEqual((rows[0]["name_rank"], rows[0]["result"]), ("J. Example, Chief Engineer", "No asbestos work since 2010 (fictitious)"))
        self.s.save_table_row("consultation", self.oid, {"id": rid, "delete": True}, BY)
        self.assertEqual(self.s.view(None, self.oid)["consultation"], [])
        actions = [e["action"] for e in self.s.store.register_log(self.oid)]
        self.assertEqual(actions[-3:], ["consultation added", "consultation changed", "consultation removed"])
        with self.assertRaises(ValueError):
            self.s.save_table_row("consultation", self.oid, {"consultation": "x"}, "")

    def test_desk_finding_checks_and_document_link(self):
        doc = self.s.upload_document(self.oid, "SDoC pump 3 (fictitious).pdf", b"%PDF-1.4 fictitious", "sdoc_md", BY)
        rid = self.s.save_table_row("desk_finding", self.oid, {"document_id": doc["id"], "supplier_component": "Pump 3", "hm_present": "no"}, BY)
        row = self.s.view(None, self.oid)["desk_findings"][0]
        self.assertEqual((row["id"], row["document"], row["hm_present"]), (rid, "SDoC pump 3 (fictitious).pdf", "no"))
        with self.assertRaisesRegex(ValueError, "yes, no or unknown"):
            self.s.save_table_row("desk_finding", self.oid, {"id": rid, "hm_present": "maybe"}, BY)
        with self.assertRaises(ValueError):
            self.s.save_table_row("desk_finding", self.oid, {"document_id": 999}, BY)

    def test_documents_with_a_chosen_kind(self):
        out = self.s.upload_document(self.oid, "Maintenance 2025.pdf", b"%PDF-1.4 fictitious", "maintenance_record", BY)
        self.assertEqual(self.s.store.document(out["id"])["kind"], "maintenance_record")
        self.s.set_document_kind(self.oid, out["id"], "previous_ihm", BY)
        self.assertEqual(self.s.store.document(out["id"])["kind"], "previous_ihm")
        with self.assertRaises(ValueError):
            self.s.upload_document(self.oid, "x.pdf", b"%PDF-1.4", "recipe", BY)
        with self.assertRaises(ValueError):
            self.s.upload_document(self.oid, "notes.txt", b"plain text", "other", BY)


class ExportedParts(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:", data_dir=tempfile.mkdtemp())
        self.oid = self.s.new_project(NEW)
        self.s.add_sample({"code": "MM-1", "source": "B01", "location": "Hold", "material": "Gasket"}, BY, self.oid)
        self.rid = self.s.ingest("Lab", "---\nMM-1 | Gasket, hold | Chrysotile 5%", object_id=self.oid)
        self.tpl = Path(tempfile.mkdtemp()) / "template.odt"
        make_template(self.tpl)

    def content(self, options=None):
        with mock.patch.object(export_odt, "report_options", lambda: options if options is not None else
                               {"vessel_rows": True, "desk_findings_table": True, "appendix_c_list": True}):
            data = export_odt.export(self.s.view(self.rid, self.oid)["report"], self.tpl)
        x = zipfile.ZipFile(io.BytesIO(data)).read("content.xml").decode()
        ET.fromstring(x)
        return x

    def text(self, xml):
        return re.sub(r"<[^>]+>", "|", xml)

    def test_project_information_gets_imo_flag_and_year_built_after_vessel_name(self):
        x = self.text(self.content())
        self.assertRegex(x, r"Vessel Name\|+MV Intake Test \(fictitious\)\|+IMO Number\|+IMO 9100001\|+Flag\|+NL\|+Year Built\|+2004")
        self.assertNotIn("IMO Number", self.text(self.content({"vessel_rows": False})))    # behind one setting

    def test_consultation_fills_the_2_2_table_by_column(self):
        self.s.save_table_row("consultation", self.oid, {"consultation": "Interview", "name_rank": "J. Example, Master", "result": "No repairs & <none> known"}, BY)
        self.s.save_table_row("consultation", self.oid, {"consultation": "Phone call", "name_rank": "A. Example, Superintendent"}, BY)
        x = self.content()
        table = re.search(r'<table:table table:name="Consult".*?</table:table>', x).group(0)
        rows = [re.findall(r"<text:p[^>]*>(.*?)</text:p>", r) for r in re.findall(r"<table:table-row>(.*?)</table:table-row>", table)]
        self.assertEqual(rows[1:], [["Interview", "J. Example, Master", "No repairs &amp; &#60;none&gt; known"],
                                    ["Phone call", "A. Example, Superintendent", "–"]])
        self.assertIn('text:style-name="TD"', table)                                       # the row's own style stays

    def test_text_that_looks_like_a_placeholder_survives_the_export(self):
        """Older bug: a value such as '<none>' was blanked to '–' by the export's last placeholder pass."""
        self.s.update_source(self.oid, "B01", {"description": "Gasket <see drawing> (fictitious)"}, BY)
        self.s.decide(self.rid, 0, "approve", BY, None, "")
        self.assertIn("Gasket &#60;see drawing&gt; (fictitious)", self.content())

    def test_empty_consultation_leaves_one_row_of_dashes(self):
        table = re.search(r'<table:table table:name="Consult".*?</table:table>', self.content()).group(0)
        self.assertEqual(re.findall(r"<text:p[^>]*>(.*?)</text:p>", re.findall(r"<table:table-row>(.*?)</table:table-row>", table)[1]), ["–", "–", "–"])

    def test_desk_findings_table_after_the_sentence_in_the_consultation_style(self):
        self.s.save_table_row("desk_finding", self.oid, {"document": "GA plan (fictitious)", "supplier_component": "Deck 2", "hm_present": "unknown", "remark": "Check on site"}, BY)
        x = self.content()
        after = x.split("presented in the following tables.</text:p>", 1)[1]
        self.assertTrue(after.startswith('<table:table table:name="DeskFindings" table:style-name="Consult">'))
        table = re.match(r"<table:table .*?</table:table>", after).group(0)
        self.assertEqual(table.count("<table:table-column "), 4)
        self.assertIn("|Document|", self.text(table))
        self.assertIn("|GA plan (fictitious)|", self.text(table))
        self.assertIn("|Unknown|", self.text(table))
        self.assertNotIn("DeskFindings", self.content({"desk_findings_table": False}))

    def test_appendix_c_lists_the_documents(self):
        self.s.upload_document(self.oid, "GA-01 general arrangement (fictitious).pdf", b"%PDF-1.4 fictitious", "ga_drawing", BY)
        x = self.content()
        app_c = x.split("Appendix C – Desk Research</text:h>", 1)[1]
        self.assertTrue(app_c.startswith('<text:p text:style-name="P9">GA-01 general arrangement (fictitious).pdf – GA drawing</text:p>'))
        self.assertIn("Fixed appendix text.", app_c)                                        # the template's own text stays
        self.assertNotIn("general arrangement (fictitious).pdf – GA drawing", self.content({"appendix_c_list": False}))


if __name__ == "__main__":
    unittest.main()
