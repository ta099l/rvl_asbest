"""Tests for the app service layer and the IHM reading (fictional demo data only)."""
import re
import unittest

from app.ihm import findings, part_i, section_2_3, sum_quantities, table_line
from app.server import Service

INSPECTOR = "Test Inspector"


def same_code(written, registered):
    """Same sample once case, hyphen, zero padding and the older M (= MM) are ignored."""
    def norm(c):
        m = re.match(r"([A-Za-z]+?)0*(\d+)$", c.replace("-", "").replace(" ", ""))
        pre = m.group(1).upper() if m else c
        return ("MM" if pre == "M" else pre) + (m.group(2) if m else "")
    return norm(written) == norm(registered)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()

    def rep(self, rid=None):
        r = self.s.view(rid)["report"]
        return r, r["id"]

    def decide_all(self, rid, careful=True):
        """Approve every proposal; a careful reviewer rejects lines whose ID does not match the proposal."""
        for x in self.s.view(rid)["report"]["rows"]:
            p = x["proposal"]["sample"]
            ok = p and (not careful or same_code(x["raw_id"], p))
            self.s.decide(rid, x["idx"], "approve" if ok else "reject", INSPECTOR, None, "")

    def test_labels_match_the_demo_artifact(self):
        r, _ = self.rep()
        labels = [x["proposal"]["label"] for x in r["rows"]]
        self.assertEqual((labels.count("certain"), labels.count("check"), labels.count("none")), (7, 1, 1))

    def test_decision_needs_name(self):
        _, rid = self.rep()
        with self.assertRaises(ValueError):
            self.s.decide(rid, 0, "approve", "", None, "")

    def test_no_link_cannot_be_approved(self):
        r, rid = self.rep()
        idx = next(x["idx"] for x in r["rows"] if x["proposal"]["label"] == "none")
        with self.assertRaises(ValueError):
            self.s.decide(rid, idx, "approve", INSPECTOR, None, "")

    def test_lab_line_keeps_certificate_and_method(self):
        r, _ = self.rep()
        self.assertEqual((r["rows"][0]["certificate"], r["rows"][0]["method"]), ("C-4471-01", "Asbestos (NEN 5896)"))

    def test_completeness_flags_missing_certificate_photo_and_result(self):
        r, _ = self.rep()
        flags = {(f["kind"], f["ref"]) for f in r["flags"]}
        self.assertIn(("completeness", "HM-1"), flags)     # no certificate number (TC07)
        self.assertIn(("completeness", "ODS-1"), flags)    # no photo
        self.assertIn(("missing", "MM-4"), flags)           # sample without a lab result
        self.assertIn(("limitation", "MM-5"), flags)        # not sampled (TC08)

    def test_only_approved_lines_reach_the_report(self):
        _, rid = self.rep()
        self.s.decide(rid, 0, "approve", INSPECTOR, None, "")
        r, _ = self.rep(rid)
        samples = [s["sample"] for sec in r["ihm"]["sections"] for s in sec["samples"]]
        self.assertEqual(samples, ["MM-1"])
        self.assertEqual([x["line"] for x in r["ihm"]["table_a"] if x["found"]], ["A-1 Asbestos"])

    def test_report_sections_follow_the_rvl_template(self):
        _, rid = self.rep()
        self.decide_all(rid)
        ihm = self.rep(rid)[0]["ihm"]
        self.assertEqual([no for no, _ in [(s["no"], 0) for s in ihm["sections"]]][:7],
                         ["2.3.1", "2.3.2", "2.3.3", "2.3.4", "2.3.5", "2.3.6", "2.3.7"])
        found = {x["line"]: x for x in ihm["table_a"] + ihm["table_b"] if x["found"]}
        self.assertEqual(sorted(found), ["A-1 Asbestos", "A-2 Polychlorinated Biphenyls (PCB)",
                                         "A-3 Ozone Depleting Substances (ODS)", "B3 Lead – Paint"])
        self.assertEqual((found["A-2 Polychlorinated Biphenyls (PCB)"]["quantity"], found["A-2 Polychlorinated Biphenyls (PCB)"]["unit"]), (35, "kg"))
        self.assertIsNone(found["A-1 Asbestos"]["quantity"])        # m and pcs: not added up, the inspector fills it in
        self.assertEqual([x["sample"] for x in ihm["part1"]["I-1"]], ["HM-1"])      # paint
        self.assertEqual([x["sample"] for x in ihm["limitations"]], ["MM-5"])
        self.assertTrue(ihm["limitations"][0]["follow_up"].startswith("Treat as potentially containing hazardous"))
        record = ihm["sections"][0]["records"][0]
        self.assertEqual((record["source"], record["certificate"], record["quantity"]), ("B01", "C-4471-01", "12 m"))
        info = dict(ihm["project"])
        self.assertEqual((info["Contractor"], info["Report Status"]), ("James", "Draft"))

    def test_signing_sets_report_status_final(self):
        _, rid = self.rep()
        self.decide_all(rid)
        self.s.sign(rid, "B. Reviewer")
        info = dict(self.rep(rid)[0]["ihm"]["project"])
        self.assertEqual((info["Report Status"], info["Report Version"]), ("Final", "1"))

    def test_report_keeps_its_evidence(self):
        r, _ = self.rep()
        e = r["evidence"]
        self.assertEqual(e["source_file"], "demo report (built in)")
        self.assertEqual(len(e["sha256"]), 64)
        self.assertEqual(e["linker_version"], e["current_linker"])
        rid = self.s.ingest("Pasted", "---\nM01 | White insulation | Chrysotile 5%")
        self.assertEqual(self.rep(rid)[0]["evidence"]["read_method"], "pasted text")


    def test_not_sampled_place_never_gets_a_link(self):
        rid = self.s.ingest("Test", "---\nM05 | Pipe insulation, void space | Chrysotile 5%")
        r, _ = self.rep(rid)
        self.assertIsNone(r["rows"][0]["proposal"]["sample"])

    def test_signing_needs_all_decisions_then_locks_the_report(self):
        _, rid = self.rep()
        with self.assertRaises(ValueError):
            self.s.sign(rid, INSPECTOR)
        self.decide_all(rid)
        self.s.sign(rid, INSPECTOR)
        r, _ = self.rep(rid)
        self.assertEqual(r["signed"]["by"], INSPECTOR)
        self.assertTrue(any("HM-1" in i for i in r["signed"]["open_items"]))
        with self.assertRaises(ValueError):
            self.s.decide(rid, 0, "reject", INSPECTOR, None, "")

    def test_processing_time_is_measured_when_all_lines_are_decided(self):
        _, rid = self.rep()
        self.assertIsNone(self.rep(rid)[0]["timing"]["minutes"])
        self.decide_all(rid)
        self.assertIsNotNone(self.rep(rid)[0]["timing"]["minutes"])

    def test_practice_review_scores_careful_and_careless_reviewers(self):
        rid = self.s.load_practice()
        r, _ = self.rep(rid)
        self.assertTrue(r["practice"])
        self.assertEqual(r["practice_score"], {"done": False, "seeded": 5})
        self.decide_all(rid, careful=True)
        self.assertEqual(self.rep(rid)[0]["practice_score"]["found"], 5)

        rid2 = self.s.load_practice()
        self.decide_all(rid2, careful=False)
        score = self.rep(rid2)[0]["practice_score"]
        self.assertEqual((score["found"], score["passed"]), (0, False))

    def test_practice_review_never_reaches_history_or_sign_off(self):
        rid = self.s.load_practice()
        self.decide_all(rid)
        with self.assertRaises(ValueError):
            self.s.sign(rid, INSPECTOR)
        with self.assertRaises(ValueError):
            self.s.save_history(rid, INSPECTOR)

    def test_seeded_lines_are_not_given_away_in_the_audit_log(self):
        rid = self.s.load_practice()
        self.decide_all(rid, careful=False)
        self.assertFalse(any("rules alone proposed" in e["text"] for e in self.rep(rid)[0]["audit"]))

    def test_follow_up_report_changes_the_history(self):
        _, rid = self.rep()
        self.decide_all(rid)
        self.s.save_history(rid, INSPECTOR)
        rid2 = self.s.load_demo("b2")
        self.decide_all(rid2)
        self.s.save_history(rid2, INSPECTOR)
        hist = self.s.view(rid2)["asset"]["samples"]["MM-3"]["history"]
        self.assertTrue(hist[-1]["changed"])


class FieldRegistration(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        self.s.new_project({"name": "MV Test (fictitious)", "site": "Test yard", "project": "J-26-099",
                            "client": "Test client (fictitious)"})

    def test_new_project_starts_empty_with_its_information(self):
        v = self.s.view(None)
        self.assertEqual((v["object"]["name"], v["register"], v["report"]), ("MV Test (fictitious)", [], None))
        self.assertEqual(self.s.store.project_info(self.s.object_id)["client"], "Test client (fictitious)")

    def test_a_project_needs_name_number_and_location(self):
        with self.assertRaises(ValueError):
            self.s.new_project({"name": "MV X", "site": "", "project": "J-1"})

    def test_register_a_sample_and_link_a_pasted_report(self):
        self.s.add_sample({"code": "MM-1", "deck": "Deck 2", "location": "Engine room", "material": "Gasket",
                           "quantity": "3", "unit": "pcs"}, INSPECTOR)
        rid = self.s.ingest("Lab", "---\nM01 | Gasket, engine room | Chrysotile 20%")
        r = self.s.view(rid)["report"]
        self.assertEqual(r["rows"][0]["proposal"]["sample"], "MM-1")

    def test_registration_needs_a_name_and_the_minimum_fields(self):
        with self.assertRaises(ValueError):
            self.s.add_sample({"code": "MM-1", "location": "Engine room", "material": "Gasket"}, "")
        with self.assertRaises(ValueError):
            self.s.add_sample({"code": "MM-1", "location": "", "material": "Gasket"}, INSPECTOR)
        with self.assertRaises(ValueError):          # not sampled without a reason
            self.s.add_sample({"code": "MM-2", "location": "Void", "material": "Insulation", "status": "not sampled"}, INSPECTOR)

    def test_a_code_cannot_be_registered_twice(self):
        self.s.add_sample({"code": "MM-1", "location": "Engine room", "material": "Gasket"}, INSPECTOR)
        with self.assertRaises(ValueError):
            self.s.add_sample({"code": "MM-1", "location": "Bridge", "material": "Tile"}, INSPECTOR)

    def test_changes_are_logged_and_the_code_never_changes(self):
        self.s.add_sample({"code": "MM-1", "location": "Engine room", "material": "Gasket"}, INSPECTOR)
        self.s.update_sample("MM-1", {"photo": "F-001", "drawing": "GA-01 pos 1"}, "Other Inspector")
        log = self.s.view(None)["register_log"]
        self.assertEqual([(e["action"], e["by"]) for e in log], [("added", INSPECTOR), ("changed", "Other Inspector")])
        self.assertIn("photo: – -> F-001", log[-1]["detail"])
        with self.assertRaises(ValueError):
            self.s.store.update_sample(self.s.object_id, "MM-1", {"code": "M99"}, INSPECTOR)

    def test_a_changed_registration_marks_the_report_out_of_date_until_read_again(self):
        self.s.add_sample({"code": "MM-1", "location": "Engine room", "material": "Gasket"}, INSPECTOR)
        rid = self.s.ingest("Lab", "---\nM02 | Floor tile, cabin | Chrysotile 2%")
        self.assertIsNone(self.s.view(rid)["report"]["rows"][0]["proposal"]["sample"])
        self.s.store.db.execute("UPDATE lab_report SET ingested_at='2000-01-01 00:00:00' WHERE id=?", (rid,))
        self.s.read_at[rid] = "2000-01-01 00:00:00"
        self.s.add_sample({"code": "MM-2", "location": "Cabin", "material": "Floor tile"}, INSPECTOR)
        self.assertTrue(self.s.view(rid)["report"]["stale"])
        self.s.reread(rid)
        r = self.s.view(rid)["report"]
        self.assertFalse(r["stale"])
        self.assertEqual(r["rows"][0]["proposal"]["sample"], "MM-2")

    def test_a_linked_sample_cannot_become_not_sampled(self):
        self.s.add_sample({"code": "MM-1", "location": "Engine room", "material": "Gasket"}, INSPECTOR)
        rid = self.s.ingest("Lab", "---\nM01 | Gasket, engine room | Chrysotile 20%")
        self.s.decide(rid, 0, "approve", INSPECTOR, None, "")
        with self.assertRaises(ValueError):
            self.s.update_sample("MM-1", {"status": "not sampled", "restriction": "No access"}, INSPECTOR)

    def test_demo_reports_only_for_the_demo_ship(self):
        with self.assertRaises(ValueError):
            self.s.load_demo("b1")


class IhmReading(unittest.TestCase):
    def one(self, result, method="", code=""):
        f = findings(result, method, code)
        self.assertEqual(len(f), 1)
        return f[0]

    def test_asbestos(self):
        self.assertEqual(self.one("Chrysotile 10–15%")["status"], "above")
        self.assertEqual(self.one("Asbestos not detected")["status"], "below")
        self.assertEqual(self.one("Chrysotile detected")["status"], "above")

    def test_substance_from_method_or_code_prefix(self):
        self.assertEqual(self.one("85 mg/kg", method="PCB (7 congeners)")["key"], "pcb")
        self.assertEqual(self.one("85 mg/kg", code="PBS-1")["key"], "pcb")

    def test_below_detection_limit(self):
        self.assertEqual(self.one("< 2 mg/kg (DL 2)", method="PCB")["status"], "below")

    def test_exactly_on_threshold_is_listed_and_flagged(self):
        f = self.one("Lead 100 mg/kg")          # the RVL template says lead 100 mg/kg (to confirm)
        self.assertEqual((f["table"], f["status"], f["value"]), ("B", "at", 100.0))

    def test_template_table_lines(self):
        self.assertEqual(table_line("pb", "Paint layer", "Railing"), "B3 Lead – Paint")
        self.assertEqual(table_line("pb", "Lead-acid", "Battery bank"), "B3 Lead – Batteries")
        self.assertIsNone(table_line("pb", "Cable sheathing", "Cable"))      # no template line: inspector
        self.assertIsNone(table_line("pfos", "Foam", "Fire system"))
        self.assertEqual(section_2_3("hg"), "2.3.6")

    def test_quantities_are_added_only_in_one_unit(self):
        self.assertEqual(sum_quantities([("12", "m"), ("3,5", "m")]), (15.5, "m"))
        self.assertEqual(sum_quantities([("12", "m"), ("4", "pcs")]), (None, ""))
        self.assertEqual(sum_quantities([("12", "m"), ("", "m")]), (None, ""))

    def test_ambiguous_number_is_not_guessed(self):
        self.assertEqual(self.one("Lead 1,400 mg/kg")["status"], "unknown")
        self.assertEqual(self.one("Lead 1.000 mg/kg")["status"], "unknown")

    def test_mixed_result_gives_one_finding_per_substance(self):
        f = findings("Cr(VI) 8 mg/kg; Pb 2100 mg/kg")
        self.assertEqual([(x["key"], x["status"]) for x in f], [("cr6", "below"), ("pb", "above")])

    def test_unreadable_result_goes_to_the_inspector(self):
        self.assertEqual(self.one("see attachment")["status"], "unknown")

    def test_part_i_list(self):
        self.assertEqual(part_i("Paint layer (3 coats)", "Railing"), "I-1")
        self.assertEqual(part_i("Cooling oil", "Transformer"), "I-2")
        self.assertEqual(part_i("Fire-resistant board", "Bulkhead", "Engine room, bulkhead"), "I-3")


if __name__ == "__main__":
    unittest.main()
