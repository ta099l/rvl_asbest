import unittest

from ai.james_ai.demo_data import SHIP, VIADUCT
from ai.james_ai.evaluate import evaluate
from ai.james_ai.linker import Sample, code_parts, id_key, link, samples_without_proposal


def run_case(case, key):
    return link(case["project"], case["samples"], case["reports"][key]["text"])


class IdKey(unittest.TestCase):
    def test_variants_match(self):
        self.assertEqual(id_key("S-03"), id_key("s-03"))
        self.assertEqual(id_key("S02"), id_key("S-02"))
        self.assertEqual(id_key("S 04"), id_key("S-04"))
        self.assertEqual(id_key("CH6-5"), id_key("CH6-05"))

    def test_different_ids_differ(self):
        self.assertNotEqual(id_key("S-03"), id_key("S-30"))
        self.assertNotEqual(id_key("CH6-01"), id_key("ZM-01"))


class ShipFirstReport(unittest.TestCase):
    def setUp(self):
        self.run_ = run_case(SHIP, "b1")
        self.p = self.run_.proposals

    def test_clean_and_tidied_ids_are_proposed(self):
        expected = {0: "S-01", 1: "S-02", 2: "S-03", 3: "S-04", 4: "S-05", 7: "S-08", 8: "S-07"}
        for i, code in expected.items():
            self.assertEqual(self.p[i].status, "propose", i)
            self.assertEqual(self.p[i].sample_id, code, i)

    def test_confidence_levels(self):
        self.assertEqual(self.p[0].confidence, "high")     # exact ID
        self.assertEqual(self.p[1].confidence, "medium")   # S02 normalised
        self.assertEqual(self.p[7].confidence, "low")      # no ID, description only

    def test_conflict_gets_no_link_and_shows_both(self):
        c = self.p[5]
        self.assertEqual(c.status, "none")
        self.assertIn("row:5:conflict", c.flags)
        self.assertEqual({a[0] for a in c.alts}, {"S-05", "S-06"})

    def test_unknown_id_gets_no_link(self):
        self.assertEqual(self.p[6].status, "none")
        self.assertIn("row:6:unknown", self.p[6].flags)

    def test_missing_sample_is_noticed(self):
        missing = [s.id for s in samples_without_proposal(SHIP["samples"], self.run_)]
        self.assertEqual(missing, ["S-06"])

    def test_no_wrong_links(self):
        r = evaluate(self.run_, SHIP["reports"]["b1"]["truth"])
        self.assertEqual(r["wrong"], 0)
        self.assertEqual((r["correct"], r["abstained_ok"], r["abstained_missed"]), (7, 1, 1))


class ShipFollowUp(unittest.TestCase):
    def test_all_exact(self):
        r = run_case(SHIP, "b2")
        self.assertEqual([p.sample_id for p in r.proposals], ["S-06", "S-03"])
        self.assertEqual(evaluate(r, SHIP["reports"]["b2"]["truth"])["wrong"], 0)


class ViaductReport(unittest.TestCase):
    def setUp(self):
        self.run_ = run_case(VIADUCT, "b1")
        self.p = self.run_.proposals

    def test_header_project_mismatch(self):
        self.assertEqual(len(self.run_.header_flags), 1)
        self.assertIn("swapped characters", self.run_.header_flags[0])

    def test_ambiguous_description_gets_no_link(self):
        self.assertEqual(self.p[4].status, "none")          # GS15: column 2 or column 3?
        self.assertIn("row:4:ambiguous", self.p[4].flags)

    def test_description_collision_gets_no_link(self):
        self.assertEqual(self.p[7].status, "none")          # CH6-13 looks like CH6-11
        self.assertIn("row:7:collision", self.p[7].flags)

    def test_padding_fixed(self):
        self.assertEqual(self.p[3].sample_id, "CH6-05")
        self.assertEqual(self.p[3].confidence, "medium")

    def test_no_wrong_links(self):
        r = evaluate(self.run_, VIADUCT["reports"]["b1"]["truth"])
        self.assertEqual(r["wrong"], 0)
        self.assertEqual((r["correct"], r["abstained_ok"], r["abstained_missed"]), (6, 1, 1))


class EdgeCases(unittest.TestCase):
    base = "Project: 26-3VK\n---\n"

    def test_empty_report(self):
        r = link("26-3VK", SHIP["samples"], "")
        self.assertEqual(r.proposals, [])

    def test_two_rows_same_sample_get_no_link(self):
        text = self.base + "S-01 | Insulation wrap, engine room bulkhead | A\nS-01 | Insulation wrap, engine room bulkhead | B"
        r = link("26-3VK", SHIP["samples"], text)
        self.assertEqual([p.status for p in r.proposals], ["none", "none"])
        self.assertTrue(all(any(f.endswith(":duplicate") for f in p.flags) for p in r.proposals))

    def test_id_without_description_is_low_confidence(self):
        r = link("26-3VK", SHIP["samples"], self.base + "S-01 |  | Asbestos not detected")
        self.assertEqual((r.proposals[0].status, r.proposals[0].confidence), ("propose", "low"))

    def test_description_with_nothing_matching(self):
        r = link("26-3VK", SHIP["samples"], self.base + "- | Anchor chain winch brake lining | X")
        self.assertEqual(r.proposals[0].status, "none")

    def test_wrong_id_with_matching_description_is_a_conflict_not_a_guess(self):
        # Lab typed S-04, but the line describes the boiler door gasket (S-03).
        r = link("26-3VK", SHIP["samples"], self.base + "S-04 | Boiler door gasket, black | X")
        self.assertEqual(r.proposals[0].status, "none")


def typed_register(*skip):
    """Fictional register with RVL-style typed codes (prefix = kind of test)."""
    rows = [
        ("M01", "Engine room, port bulkhead", "Insulation wrap", "grey fibrous"),
        ("M12", "Cargo hold 1", "Bulkhead paint, asbestos check", "red-brown"),
        ("HM12", "Cargo hold 1", "Bulkhead paint, heavy metals", "red-brown"),
        ("PBS03", "Engine room, main switchboard", "Cable sheath", "black"),
        ("OS01", "Steering gear room", "Hydraulic oil", "amber"),
    ]
    return [Sample(c, "", loc, "", mat, col) for c, loc, mat, col in rows if c not in skip]


class TypedCodes(unittest.TestCase):
    def one(self, line, register=None):
        return link("", register or typed_register(), "---\n" + line).proposals[0]

    def test_code_parts_splits_prefix_and_number(self):
        for raw in ("PBS3", "PBS03", "PBS 03", "pbs-03", "PBS-3"):
            self.assertEqual(code_parts(raw), ("PBS", "3"), raw)
        self.assertEqual(code_parts("CH6-05"), ("CH6", "5"))
        self.assertIsNone(code_parts("S-O3"))               # letter O, not a number

    def test_chromium_6_prefix_keeps_its_digit(self):
        for raw in ("CR601", "CR6-01", "CR6 01", "cr6-1"):
            self.assertEqual(code_parts(raw), ("CR6", "1"), raw)
        self.assertEqual(code_parts("CR610"), ("CR6", "10"))
        self.assertEqual(id_key("CH601"), id_key("CH6-01"))
        self.assertNotEqual(id_key("CR601"), id_key("CH601"))

    def test_prefix_is_part_of_the_code(self):
        self.assertNotEqual(id_key("M12"), id_key("HM12"))
        self.assertEqual(id_key("PBS1"), id_key("PBS01"))

    def test_spacing_and_padding_link_the_same_code(self):
        p = self.one("PBS 3 | Cable sheath, main switchboard engine room | PCB 12 mg/kg")
        self.assertEqual((p.sample_id, p.confidence), ("PBS03", "medium"))

    def test_prefix_conflict_gets_no_link_and_says_why(self):
        p = self.one("M12 | Red-brown paint, cargo hold 1, heavy metals | Pb 640 mg/kg")
        self.assertEqual(p.status, "none")
        self.assertIn("row:0:prefix_conflict", p.flags)
        self.assertEqual({a[0] for a in p.alts}, {"M12", "HM12"})
        self.assertIn("differ only by prefix", p.reason)

    def test_id_decides_when_description_fits_both_equally(self):
        p = self.one("HM12 | Red-brown paint, cargo hold 1 | Pb 640 mg/kg")
        self.assertEqual((p.sample_id, p.confidence), ("HM12", "high"))

    def test_matching_prefix_and_description_links(self):
        p = self.one("M12 | Bulkhead paint cargo hold 1, asbestos check | Not detected")
        self.assertEqual(p.sample_id, "M12")

    def test_unregistered_code_of_a_known_family_is_not_guessed(self):
        p = self.one("OS02 | Hydraulic oil, steering gear | PCB < 1 mg/kg")
        self.assertEqual(p.status, "none")
        self.assertIn("row:0:unregistered", p.flags)
        self.assertIn("not registered", p.reason)
        self.assertEqual(p.alts[0][0], "OS01")              # shown as a hint, not proposed

    def test_unknown_code_with_other_prefix_same_number_is_not_guessed(self):
        # No M codes at all here, but the description fits HM12: still another test.
        reg = typed_register("M01", "M12")
        p = self.one("M12 | Red-brown paint, cargo hold 1, heavy metals | Pb 640 mg/kg", reg)
        self.assertEqual(p.status, "none")
        self.assertIn("prefix HM", p.reason)

    def test_code_from_another_system_may_still_match_on_description(self):
        # A lab's own numbering (XY7) says nothing about our register: low-confidence guess stays.
        p = self.one("XY7 | Hydraulic oil, steering gear | PCB < 1 mg/kg")
        self.assertEqual((p.sample_id, p.confidence), ("OS01", "low"))

    def test_malformed_code_may_still_match_on_description(self):
        p = link("", SHIP["samples"], "---\nS-O3 | Boiler door seal, black | X").proposals[0]
        self.assertEqual((p.sample_id, p.confidence), ("S-03", "low"))


def standard_register():
    """Codes in RVL's standard notation: IHM prefix, dash, no leading zeros (Rolf, 6 Nov 2026)."""
    rows = [
        ("MM-1", "Engine room", "Pipe lagging", "grey fibrous"),
        ("MM-2", "Boiler room", "Boiler door gasket", "black"),
        ("CR6-1", "Cargo hold 2", "Primer layer on hatch coaming", "yellow"),
        ("PAH-1", "Deck 1", "Bituminous deck covering", "black"),
        ("HM-1", "Accommodation", "Railing paint", "red"),
    ]
    return [Sample(c, "", loc, "", mat, col) for c, loc, mat, col in rows]


class StandardCodesAndAliases(unittest.TestCase):
    def one(self, line):
        return link("", standard_register(), "---\n" + line).proposals[0]

    def test_padded_lab_code_matches_the_standard_code(self):
        p = self.one("MM01 | Pipe lagging, engine room | Chrysotile 5%")
        self.assertEqual((p.sample_id, p.confidence), ("MM-1", "medium"))

    def test_older_notation_is_read_through_the_alias_table(self):
        for raw, sid in (("CH6-01", "CR6-1"), ("Pac-01", "PAH-1"), ("M02", "MM-2")):
            p = self.one(f"{raw} | " + {"CR6-1": "Primer hatch coaming, cargo hold 2",
                                         "PAH-1": "Bituminous deck covering, deck 1",
                                         "MM-2": "Boiler door gasket, boiler room"}[sid] + " | X")
            self.assertEqual(p.sample_id, sid, raw)
            self.assertEqual(p.confidence, "medium", raw)       # never high through an alias
            self.assertIn("older notation", p.reason)

    def test_exact_standard_code_stays_high(self):
        p = self.one("CR6-1 | Primer hatch coaming, cargo hold 2 | Cr(VI) 120 mg/kg")
        self.assertEqual((p.sample_id, p.confidence), ("CR6-1", "high"))

    def test_unregistered_number_in_old_notation_is_not_guessed(self):
        # M3 next to MM-1 and MM-2: a sample nobody registered, even in the old notation.
        p = self.one("M3 | Boiler door gasket, boiler room | Chrysotile 40%")
        self.assertEqual(p.status, "none")
        self.assertIn("row:0:unregistered", p.flags)

    def test_alias_does_not_join_different_tests(self):
        # M is asbestos (MM), HM is heavy metals: M1 must not become HM-1.
        p = self.one("M1 | Railing paint, accommodation | Pb 300 mg/kg")
        self.assertNotEqual(p.sample_id, "HM-1")


if __name__ == "__main__":
    unittest.main()
