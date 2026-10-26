import copy
import json
import os
import unittest

from ai.james_ai.contract import (ContractError, check_request, response_problems,
                                  validate_response)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(*parts):
    with open(os.path.join(ROOT, "contract", *parts), encoding="utf-8") as f:
        return json.load(f)


REQUEST = load("examples", "request.json")
GOOD = load("examples", "response.json")


def broken(change):
    """A copy of the good answer with one thing broken."""
    r = copy.deepcopy(GOOD)
    change(r)
    return r


class ValidAnswers(unittest.TestCase):
    def test_examples_follow_the_contract(self):
        check_request(REQUEST)
        resp, problems = validate_response(GOOD, REQUEST)
        self.assertEqual(problems, [])
        self.assertEqual(resp, GOOD)

    def test_raw_text_is_parsed(self):
        resp, problems = validate_response(json.dumps(GOOD), REQUEST)
        self.assertEqual(problems, [])
        self.assertEqual(resp["proposals"][0]["sample"], "S-02")

    def test_no_link_may_carry_a_confidence(self):
        ans = broken(lambda r: r["proposals"][2].update(confidence="high"))
        self.assertEqual(validate_response(ans, REQUEST)[1], [])

    def test_result_is_a_copy(self):
        resp, _ = validate_response(GOOD, REQUEST)
        resp["proposals"][0]["sample"] = "S-03"
        self.assertEqual(GOOD["proposals"][0]["sample"], "S-02")


class BrokenAnswersBecomeNoLink(unittest.TestCase):
    """Every broken answer must turn ALL rows into no link, never a partial guess."""

    CASES = {
        "not JSON": "Sure! Line 1 is S-02.",
        "JSON in a code fence": "```json\n" + json.dumps(GOOD) + "\n```",
        "bare list (the v1 prompt format)": json.dumps(GOOD["proposals"]),
        "one line missing": broken(lambda r: r["proposals"].pop()),
        "one line extra": broken(lambda r: r["proposals"].append(dict(r["proposals"][0], n=4))),
        "lines out of order": broken(lambda r: r["proposals"].reverse()),
        "invented code": broken(lambda r: r["proposals"][1].update(sample="S-09")),
        "code spelled differently": broken(lambda r: r["proposals"][0].update(sample="S02")),
        "code in lower case": broken(lambda r: r["proposals"][0].update(sample="s-02")),
        "confidence not allowed": broken(lambda r: r["proposals"][0].update(confidence="very high")),
        "link without confidence": broken(lambda r: r["proposals"][0].update(confidence=None)),
        "n is true instead of 1": broken(lambda r: r["proposals"][0].update(n=True)),
        "n is text": broken(lambda r: r["proposals"][0].update(n="1")),
        "empty reason": broken(lambda r: r["proposals"][0].update(reason="  ")),
        "missing reason": broken(lambda r: r["proposals"][0].pop("reason")),
        "extra field": broken(lambda r: r["proposals"][0].update(certainty=0.9)),
        "extra top-level field": broken(lambda r: r.update(note="done")),
        "sample is a number": broken(lambda r: r["proposals"][0].update(sample=2)),
        "proposals is not a list": {"proposals": "S-02, S-01, none"},
        "null answer": "null",
    }

    def test_each_broken_answer_is_rejected(self):
        for name, answer in self.CASES.items():
            with self.subTest(name):
                resp, problems = validate_response(answer, REQUEST)
                self.assertTrue(problems, "should have been rejected")
                self.assertEqual([p["n"] for p in resp["proposals"]], [1, 2, 3])
                for p in resp["proposals"]:
                    self.assertIsNone(p["sample"])
                    self.assertIsNone(p["confidence"])
                    self.assertIn("AI answer rejected", p["reason"])
                # the safe replacement must itself follow the contract
                self.assertEqual(response_problems(resp, REQUEST), [])

    def test_reason_names_the_problem(self):
        resp, problems = validate_response(self.CASES["invented code"], REQUEST)
        self.assertEqual(problems, ["proposal 2: sample 'S-09' is not a code in the register"])
        self.assertIn("S-09", resp["proposals"][0]["reason"])


class BrokenRequests(unittest.TestCase):
    """A broken request is an app bug: it must stop loudly, not become 'no link'."""

    def assert_rejected(self, change, fragment):
        req = copy.deepcopy(REQUEST)
        change(req)
        with self.assertRaises(ContractError) as ctx:
            validate_response(GOOD, req)
        self.assertIn(fragment, str(ctx.exception))

    def test_duplicate_register_code(self):
        self.assert_rejected(lambda r: r["register"][1].update(code="S-01"), "appears twice")

    def test_rows_not_numbered_in_order(self):
        self.assert_rejected(lambda r: r["rows"][1].update(n=5), "n must be 2")

    def test_missing_field(self):
        self.assert_rejected(lambda r: r["register"][0].pop("colour"), "missing colour")

    def test_empty_rows(self):
        self.assert_rejected(lambda r: r.update(rows=[]), "rows must be a non-empty list")


class SchemaFilesAgree(unittest.TestCase):
    """The schema files are what Ivan reads; check they accept and reject like the code."""

    def setUp(self):
        try:
            import jsonschema  # optional, only for this check
        except ImportError:
            self.skipTest("jsonschema not installed (pip install jsonschema)")
        self.v_req = jsonschema.Draft202012Validator(load("request.schema.json"))
        self.v_resp = jsonschema.Draft202012Validator(load("response.schema.json"))

    def test_examples_match_schemas(self):
        self.assertEqual(list(self.v_req.iter_errors(REQUEST)), [])
        self.assertEqual(list(self.v_resp.iter_errors(GOOD)), [])

    def test_schema_rejects_shape_errors(self):
        # The register and n-order rules need the request, so only shape errors here.
        for name in ("bare list (the v1 prompt format)", "confidence not allowed",
                     "link without confidence", "n is true instead of 1", "empty reason",
                     "extra field", "missing reason"):
            with self.subTest(name):
                ans = self.CASES_[name]
                ans = json.loads(ans) if isinstance(ans, str) else ans
                self.assertTrue(list(self.v_resp.iter_errors(ans)))

    CASES_ = BrokenAnswersBecomeNoLink.CASES


if __name__ == "__main__":
    unittest.main()
