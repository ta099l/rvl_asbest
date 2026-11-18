"""The bronbladen payload and statuses (fictional demo data only)."""
import io
import json
import tempfile
import unittest

from PIL import Image

from app.server import Service

BY = "Test Inspector (fictitious)"


def jpeg(colour) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (32, 24), colour).save(b, "JPEG")
    return b.getvalue()


class Bronbladen(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:", data_dir=tempfile.mkdtemp())
        self.oid = self.s.demo_object
        self.rid = self.s.view(None, self.oid)["report"]["id"]
        self.n = 0

    def bb(self, no):
        return next(b for b in self.s.view(None, self.oid)["bronbladen"] if b["no"] == no)

    def idx(self, raw_id):
        return next(x["idx"] for x in self.s.view(self.rid, self.oid)["report"]["rows"] if x["raw_id"] == raw_id)

    def photo(self, name):
        self.n += 1
        out = self.s.upload_photo(self.oid, name, jpeg((self.n * 37 % 255, 80, 140)), BY)
        self.s.accept_photo_proposals(self.oid, BY)
        return out["id"]

    def test_every_demo_source_in_group_order(self):
        bbs = self.s.view(None, self.oid)["bronbladen"]
        self.assertEqual([b["no"] for b in bbs], ["B01", "B02", "B03", "B04", "B10", "B05", "B06", "B09", "B08", "B07"])
        self.assertEqual([b["group"] for b in bbs][:5], ["asbestos"] * 5)
        b01 = bbs[0]
        self.assertEqual([x["code"] for x in b01["samples"]], ["MM-1"])
        self.assertEqual((b01["description"], b01["condition"], b01["quantity"], b01["unit"]), ("Exhaust pipe, Insulation", "Damaged", "12", "m"))

    def test_lab_values_only_from_approved_lines(self):
        b = self.bb("B01")
        self.assertEqual([(l["state"], l["sample"]) for l in b["lab"]], [("waiting", "MM-1")])
        self.assertNotIn("Chrysotile", json.dumps(b))                   # no value before an inspector approved it
        self.assertEqual((b["results"], b["certificates"]), ([], []))
        self.s.decide(self.rid, self.idx("MM-1"), "approve", BY, None, "")
        b = self.bb("B01")
        self.assertEqual(b["lab"][0]["state"], "approved")
        self.assertEqual((b["lab"][0]["certificate"], b["lab"][0]["result"]), ("C-4471-01", "Chrysotile 10–15%"))
        self.assertEqual((b["results"], b["certificates"]), (["MM-1: Chrysotile 10–15%"], ["C-4471-01"]))
        self.assertIn("This concerns Asbestos", b["conclusion_auto"])

    def test_a_rejected_line_is_shown_as_rejected_without_its_value(self):
        self.s.decide(self.rid, self.idx("MM-2"), "reject", BY, None, "wrong sample")
        b = self.bb("B02")
        self.assertEqual([(l["state"], l["sample"]) for l in b["lab"]], [("rejected", "MM-2")])
        self.assertNotIn("result", b["lab"][0])
        self.assertEqual(b["status"], "attention")

    def test_unapproving_turns_the_bronblad_to_needs_attention(self):
        self.photo("MM-1 F-012 pipe.jpg")
        self.s.decide(self.rid, self.idx("MM-1"), "approve", BY, None, "")
        self.assertEqual(self.bb("B01")["status"], "complete")
        self.s.decide(self.rid, self.idx("MM-1"), "reject", BY, None, "changed my mind")      # Change decision -> Reject
        b = self.bb("B01")
        self.assertEqual(b["status"], "attention")
        self.assertIn("MM-1 has no approved lab result", " ".join(i["text"] for i in b["issues"]))

    def test_a_corrected_line_moves_to_the_corrected_samples_bronblad(self):
        idx = self.idx("M-03")                                           # the agent proposed MM-3 (B03)
        self.assertEqual(self.bb("B03")["lab"][0]["state"], "waiting")
        self.s.decide(self.rid, idx, "correct", BY, "MM-4", "it is the bulkhead board")
        self.assertEqual(self.bb("B03")["lab"], [])                     # gone from the original one
        b04 = self.bb("B04")
        self.assertEqual([(l["state"], l["sample"], l["result"]) for l in b04["lab"]],
                         [("approved", "MM-4", "Chrysotile + amosite 5–10%")])

    def test_photos_in_upload_order_and_more_than_four_flagged(self):
        ids = [self.photo(f"MM-2_{k} tile.jpg") for k in range(5)]
        b = self.bb("B02")
        with_file = [p["id"] for p in b["photos"] if p["file"]]
        self.assertEqual(with_file, ids)                                # upload order
        self.assertEqual(b["photos"][0]["photo_no"], "F-018")          # the registered number came first
        self.assertEqual((b["photo_files"], b["too_many_photos"]), (5, True))
        self.assertEqual(len(b["photos"]), 6)                           # all of them: the screen shows 4 and "+2 more"
        self.s.update_photo(self.oid, ids[-1], {"link": ""}, BY)
        self.assertFalse(self.bb("B02")["too_many_photos"])

    def test_status_not_accessible_and_complete(self):
        self.assertEqual(self.bb("B10")["status"], "not_accessible")    # MM-5: no access, PCHM
        self.photo("PBS-2 F-057 window.jpg")
        self.s.decide(self.rid, self.idx("PBS-2"), "approve", BY, None, "")
        self.assertEqual(self.bb("B09")["status"], "complete")
        self.s.update_source(self.oid, "B09", {"assessment": "not accessible"}, BY)
        self.assertEqual(self.bb("B09")["status"], "not_accessible")

    def test_autosave_checks_and_logs(self):
        self.s.update_source(self.oid, "B01", {"condition": "Weathered", "conclusion": "Remove before hot work."}, BY)
        b = self.bb("B01")
        self.assertEqual((b["condition"], b["conclusion"]), ("Weathered", "Remove before hot work."))
        log = self.s.store.register_log(self.oid)[-1]
        self.assertEqual((log["code"], log["action"], log["changed_by"]), ("B01", "source changed", BY))
        with self.assertRaises(ValueError):
            self.s.update_source(self.oid, "B01", {"condition": "Rusty"}, BY)
        with self.assertRaises(ValueError):
            self.s.update_source(self.oid, "B01", {"condition": "Good"}, "")

    def test_new_source_takes_the_next_number_and_unlinked_samples_and_photos(self):
        self.s.add_sample({"code": "PBS-3", "location": "Bridge", "material": "Kit"}, BY, self.oid)
        pid = self.s.upload_photo(self.oid, "overview bridge.jpg", jpeg("gray"), BY)["id"]
        no = self.s.new_source(self.oid, "pcb", ["PBS-3"], [pid], BY)
        self.assertEqual(no, "B11")
        b = self.bb("B11")
        self.assertEqual((b["group"], [x["code"] for x in b["samples"]], [p["id"] for p in b["photos"]]), ("pcb", ["PBS-3"], [pid]))
        actions = [(e["code"], e["action"]) for e in self.s.store.register_log(self.oid)]
        self.assertIn(("B11", "source added"), actions)
        with self.assertRaisesRegex(ValueError, "already belongs to source"):
            self.s.new_source(self.oid, "pcb", ["PBS-1"], [], BY)


if __name__ == "__main__":
    unittest.main()
