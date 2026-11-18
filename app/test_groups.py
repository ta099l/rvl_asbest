"""Substance groups for the fieldwork tabs (fictional data only).

One mapping (app/ihm.py PREFIX_GROUP) decides both the tab and the report section, through
section_2_3, so a sample's tab and the section it appears under in the export never disagree.
"""
import unittest

from app.ihm import group_for_code, next_code
from app.server import Service

INSPECTOR = "Test Inspector"


def where(code):
    g = group_for_code(code)
    return g["key"], g["section"], g["unknown"]


class GroupForCode(unittest.TestCase):
    def test_every_listed_prefix(self):
        expected = {
            "MM-1": ("asbestos", "2.3.1"), "KM-1": ("asbestos", "2.3.1"),
            "PBS-1": ("pcb", "2.3.2"), "SS-1": ("pcb", "2.3.2"), "OS-1": ("pcb", "2.3.2"),
            "ODS-1": ("ods", "2.3.3"),
            "PFOS-1": ("pfos", "2.3.4"), "PFAS-1": ("pfos", "2.3.4"),
            "HBCDD-1": ("hbcdd", "2.3.5"),
            "HM-1": ("metals", "2.3.6"), "CR6-1": ("metals", "2.3.6"),
            "NORM-1": ("radio", "2.3.7"),
            "PAH-1": ("other", "2.3.x"), "TBT-1": ("other", "2.3.x"), "TPH-1": ("other", "2.3.x"),
            "VOC-1": ("other", "2.3.x"), "VI-1": ("other", "2.3.x"), "V-1": ("other", "2.3.x"),
            "DR-1": ("other", "2.3.x"), "EI-1": ("other", "2.3.x"),
        }
        for code, (group, section) in expected.items():
            with self.subTest(code=code):
                self.assertEqual(where(code), (group, section, False))

    def test_older_notations_follow_the_linker_aliases(self):
        self.assertEqual(where("M-12"), ("asbestos", "2.3.1", False))   # M = MM
        self.assertEqual(where("ZM-03"), ("metals", "2.3.6", False))    # ZM = HM (zware metalen)
        self.assertEqual(where("Pac-01"), ("other", "2.3.x", False))    # PAC = PAH
        self.assertEqual(where("CH6-02"), ("metals", "2.3.6", False))   # CH6 = CR6

    def test_prefixes_that_look_alike_stay_apart(self):
        self.assertEqual(where("M12")[0], "asbestos")
        self.assertEqual(where("MM12")[0], "asbestos")
        self.assertEqual(where("HM12")[0], "metals")         # HM12 never matches M
        self.assertEqual(where("ZM12")[0], "metals")
        self.assertEqual(where("PBS03")[0], "pcb")
        self.assertEqual(where("SS03")[0], "pcb")
        self.assertEqual(group_for_code("PBS03")["prefix"], "PBS")
        self.assertEqual(group_for_code("SS03")["prefix"], "SS")

    def test_spelling_does_not_matter(self):
        for code in ("hm12", "HM-12", "HM 12", "hm-012", "Hm12"):
            with self.subTest(code=code):
                self.assertEqual(where(code), ("metals", "2.3.6", False))
        self.assertEqual(where("cr603"), ("metals", "2.3.6", False))    # digit prefix without separator
        self.assertEqual(where("pbs 3"), ("pcb", "2.3.2", False))

    def test_unknown_prefix_goes_to_other_with_a_warning(self):
        for code in ("MI02", "XX-1", "S-02", "A-14", "no code"):
            with self.subTest(code=code):
                self.assertEqual(where(code), ("other", "2.3.x", True))

    def test_known_codes_without_a_lab_sample_have_no_warning_but_a_meaning(self):
        for code in ("VI-1", "DR-1", "EI-1", "V00"):
            with self.subTest(code=code):
                g = group_for_code(code)
                self.assertFalse(g["unknown"])
                self.assertIn("no lab sample", g["meaning"])

    def test_pfas_is_labelled_so_it_is_not_read_as_pfos(self):
        self.assertEqual(group_for_code("PFAS-1")["label"], "PFOS / PFAS")


class NextCode(unittest.TestCase):
    def test_follows_the_style_the_project_uses(self):
        self.assertEqual(next_code(["M01", "M02"], "asbestos"), "M03")
        self.assertEqual(next_code(["PBS01", "PBS03"], "pcb"), "PBS04")
        self.assertEqual(next_code(["MM-1", "MM-5"], "asbestos"), "MM-6")
        self.assertEqual(next_code(["M02", "MM-5"], "asbestos"), "MM-6")      # M00 and MM00 both count

    def test_other_prefixes_in_the_group_do_not_count(self):
        self.assertEqual(next_code(["SS-7", "PBS-2"], "pcb"), "PBS-3")
        self.assertEqual(next_code(["HM-1", "M-9"], "metals"), "HM-2")         # M is asbestos, not HM

    def test_empty_group_starts_in_rvl_standard_form(self):
        self.assertEqual(next_code([], "asbestos"), "MM-1")
        self.assertEqual(next_code(["PBS-1"], "metals"), "HM-1")

    def test_other_has_no_main_prefix(self):
        self.assertIsNone(next_code(["PAH-1"], "other"))


class TabsInTheView(unittest.TestCase):
    def setUp(self):
        self.s = Service()

    def test_demo_ship_tabs_and_counts(self):
        v = self.s.view(None, self.s.demo_object)
        counts = {g["key"]: g["count"] for g in v["groups"]}
        self.assertEqual((counts["asbestos"], counts["pcb"], counts["metals"]), (5, 3, 1))
        by_tab = {}
        for x in v["register"]:
            by_tab.setdefault(x["group"]["key"], []).append(x["code"])
        self.assertEqual(by_tab["asbestos"], ["MM-1", "MM-2", "MM-3", "MM-4", "MM-5"])
        self.assertEqual(sorted(by_tab["pcb"]), ["OS-1", "PBS-1", "PBS-2"])
        self.assertEqual(by_tab["metals"], ["HM-1"])
        self.assertEqual([g["key"] for g in v["groups"] if g["always"]], ["asbestos", "pcb", "metals"])

    def test_hm12_and_m12_in_one_project_land_in_different_tabs(self):
        oid = self.s.new_project({"name": "MV Groups (fictitious)", "site": "Yard", "project": "J-26-400"})
        for code, material in (("M12", "Gasket"), ("HM12", "Railing paint"), ("ZM-03", "Hatch paint"), ("MI02", "Tile")):
            self.s.add_sample({"code": code, "location": "Deck 1", "material": material}, INSPECTOR, oid)
        v = self.s.view(None, oid)
        tab = {x["code"]: (x["group"]["key"], x["group"]["unknown"]) for x in v["register"]}
        self.assertEqual(tab, {"M12": ("asbestos", False), "HM12": ("metals", False),
                               "ZM-03": ("metals", False), "MI02": ("other", True)})
        g = {x["key"]: x for x in v["groups"]}
        self.assertEqual((g["asbestos"]["next_code"], g["metals"]["next_code"]), ("M13", "HM13"))
        self.assertEqual((g["other"]["count"], g["other"]["unknown"]), (1, 1))

    def test_tab_section_equals_export_section_for_every_demo_sample(self):
        oid = self.s.demo_object
        rids = [r["id"] for r in self.s.view(None, oid)["reports"]] + [self.s.load_demo("b2", oid)]
        seen = 0
        for rid in rids:
            for x in self.s.view(rid, oid)["report"]["rows"]:
                if x["proposal"]["sample"]:
                    self.s.decide(rid, x["idx"], "approve", INSPECTOR, None, "")
            for sec in self.s.view(rid, oid)["report"]["ihm"]["sections"]:
                for rec in sec["records"]:
                    with self.subTest(report=rid, sample=rec["sample"]):
                        self.assertEqual(group_for_code(rec["sample"])["section"], sec["no"])
                    seen += 1
        self.assertGreaterEqual(seen, 9)          # the check really ran over the demo samples


if __name__ == "__main__":
    unittest.main()
