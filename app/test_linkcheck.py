"""The link check: every rule can be produced with the demo data and disappears after its fix (fictional data only)."""
import io
import tempfile
import unittest

from PIL import Image

from app.server import Service

BY = "Test Inspector (fictitious)"


def jpeg(colour) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (32, 24), colour).save(b, "JPEG")
    return b.getvalue()


class LinkCheck(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:", data_dir=tempfile.mkdtemp())
        self.oid = self.s.demo_object
        self.rid = self.s.view(None, self.oid)["report"]["id"]
        self.n = 0

    def issues(self, rule):
        return [i for i in self.s.link_check(self.oid) if i["rule"] == rule]

    def upload(self, name):
        self.n += 1
        return self.s.upload_photo(self.oid, name, jpeg((self.n * 40 % 255, 90, 120)), BY)

    def line(self, raw_id):
        return next(x for x in self.s.view(self.rid, self.oid)["report"]["rows"] if x["raw_id"] == raw_id)

    def test_photo_not_linked(self):
        out = self.upload("overview engine room.jpg")
        issue = [i for i in self.issues("photo_unlinked") if i["fix"]["photo"] == out["id"]]
        self.assertEqual(len(issue), 1)
        self.s.update_photo(self.oid, out["id"], {"link": "source:B04"}, BY)
        self.assertFalse([i for i in self.issues("photo_unlinked") if i["fix"]["photo"] == out["id"]])

    def test_source_without_photo(self):
        self.assertIn("B01", " ".join(i["text"] for i in self.issues("source_no_photo")))   # rows without a file
        self.upload("MM-1 F-012 pipe.jpg")
        self.assertNotIn("Source B01 ", " ".join(i["text"] for i in self.issues("source_no_photo")))

    def test_source_with_more_than_four_photos(self):
        ids = [self.upload(f"MM-1_{k} pipe.jpg")["id"] for k in range(5)]
        self.s.accept_photo_proposals(self.oid, BY)
        self.assertEqual(len(self.issues("source_too_many")), 1)
        self.s.update_photo(self.oid, ids[-1], {"link": ""}, BY)                  # unlink the extra one
        self.assertFalse(self.issues("source_too_many"))

    def test_sample_without_source(self):
        self.s.add_sample({"code": "PBS-3", "location": "Bridge", "material": "Kit"}, BY, self.oid)
        issue = self.issues("sample_no_source")
        self.assertEqual([(i["fix"]["page"], i["fix"]["sample"]) for i in issue], [("fieldwork", "PBS-3")])
        self.s.update_sample("PBS-3", {"source": "B11"}, BY, self.oid)
        self.assertFalse(self.issues("sample_no_source"))

    def test_sample_without_approved_result(self):
        self.assertIn("Sample MM-1 has", " ".join(i["text"] for i in self.issues("sample_no_result")))
        fix = next(i["fix"] for i in self.issues("sample_no_result") if "MM-1 " in i["text"])
        self.assertEqual((fix["page"], fix["report"]), ("lab", self.rid))         # opens its lab line
        self.s.decide(self.rid, self.line("MM-1")["idx"], "approve", BY, None, "")
        self.assertNotIn("Sample MM-1 has", " ".join(i["text"] for i in self.issues("sample_no_result")))
        mm4 = next(i for i in self.issues("sample_no_result") if "MM-4" in i["text"])
        self.assertEqual(mm4["fix"]["page"], "fieldwork")                          # no lab line in this report

    def test_approved_result_without_certificate(self):
        idx = self.line("HM-1")["idx"]
        self.s.decide(self.rid, idx, "approve", BY, None, "")
        issue = self.issues("result_no_certificate")
        self.assertEqual([(i["fix"]["page"], i["fix"]["line"]) for i in issue], [("lab", idx)])
        self.s.set_certificate(self.rid, idx, "C-4471-07", BY)
        self.assertFalse(self.issues("result_no_certificate"))
        with self.assertRaisesRegex(ValueError, "already has a certificate"):      # the lab's number is never changed
            self.s.set_certificate(self.rid, self.line("MM-1")["idx"], "C-999", BY)
        log = self.s.store.register_log(self.oid)[-1]
        self.assertEqual((log["action"], log["changed_by"]), ("lab certificate added", BY))

    def test_lab_line_code_not_in_register(self):
        self.assertEqual([i["fix"]["line"] for i in self.issues("code_not_in_register")], [self.line("MM-9")["idx"]])
        self.s.decide(self.rid, self.line("MM-9")["idx"], "reject", BY, None, "not ours")
        self.assertFalse(self.issues("code_not_in_register"))

    def test_same_sample_twice_is_an_error_and_cannot_be_registered_now(self):
        with self.assertRaisesRegex(ValueError, "same sample as MM-3"):
            self.s.add_sample({"code": "M-3", "location": "Hold", "material": "Gasket"}, BY, self.oid)
        # an older file can still hold both: the check shows it as an error
        self.s.store.db.execute("INSERT INTO sample(object_id,code,source,location,part,material,status) "
                                "VALUES (?,?,?,?,?,?,?)", (self.oid, "M-3", "B03", "Flange", "", "Gasket", "sampled"))
        issue = self.issues("same_sample_twice")
        self.assertEqual([i["severity"] for i in issue], ["error"])
        self.assertIn("MM-3 and M-3", issue[0]["text"])

    def test_prefix_only_is_a_warning_that_can_be_marked_checked(self):
        warn = self.issues("prefix_only")
        self.assertEqual(sorted(i["key"] for i in warn), ["MM-1/HM-1", "OS-1/ODS-1"])
        self.assertTrue(all(i["severity"] == "warning" for i in warn))
        self.s.confirm_check(self.oid, "MM-1/HM-1", BY)
        self.assertEqual([i["key"] for i in self.issues("prefix_only")], ["OS-1/ODS-1"])
        with self.assertRaises(ValueError):                                        # only an open warning can be checked
            self.s.confirm_check(self.oid, "anything", BY)
        log = self.s.store.register_log(self.oid)[-1]
        self.assertEqual((log["code"], log["action"], log["changed_by"]), ("MM-1/HM-1", "check confirmed", BY))

    def test_errors_come_first_and_the_report_uses_the_same_list(self):
        issues = self.s.link_check(self.oid)
        sev = [i["severity"] for i in issues]
        self.assertEqual(sev, sorted(sev, key=lambda x: x != "error"))
        open_items = self.s.view(self.rid, self.oid)["report"]["open_items"]
        self.assertEqual(sum(o.startswith("Link check") for o in open_items), len(issues))
        self.assertEqual(self.s.view(None, self.oid)["link_check"], issues)

    def test_all_links_complete_is_possible(self):
        oid = self.s.new_project({"name": "MV Complete (fictitious)", "site": "Yard", "project": "J-26-800"})
        self.s.add_sample({"code": "MM-1", "source": "B01", "location": "Hold", "material": "Gasket"}, BY, oid)
        rid = self.s.ingest("Lab", "Columns: Sample No. | Description | Result | Certificate\n---\n"
                                   "MM-1 | Gasket, hold | Chrysotile 5% | C-1", object_id=oid)
        self.s.decide(rid, 0, "approve", BY, None, "")
        out = self.s.upload_photo(oid, "MM-1.jpg", jpeg("gray"), BY)
        self.assertEqual(self.s.accept_photo_proposals(oid, BY), 1)
        self.assertEqual(self.s.link_check(oid), [], self.s.link_check(oid))
        self.assertTrue(out["linked"])


if __name__ == "__main__":
    unittest.main()
