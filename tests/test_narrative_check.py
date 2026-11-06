"""Tests for the narrative claim check (scripts/narrative_check.py and its copy in build_report.js).
Run from the repo root: python -m unittest discover tests"""
import copy, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import cost_model  # noqa: E402
from narrative_check import check  # noqa: E402

EXAMPLE = os.path.join(ROOT, "assets", "example")


def load(name):
    with open(os.path.join(EXAMPLE, name), encoding="utf-8") as f:
        return json.load(f)


def costs_complete():
    return cost_model.compute(load("prices.json"), load("workload.json"))


def costs_incomplete():
    p = load("prices.json")
    aws = p["clouds"]["aws"]
    aws[:] = [l for l in aws if l["component"] != "web"]
    aws.append({"component": "web", "item": "EC2 m7i.large", "source": "unpriced", "note": "not found"})
    return cost_model.compute(p, load("workload.json"))


def report_with(summary=None, pros_cons=None):
    r = {"title": "T", "executive_summary": summary or [], "variance_discussion": []}
    if pros_cons:
        r["pros_cons"] = pros_cons
    return r


class IncompleteComparison(unittest.TestCase):
    """Reviewer suggestion: narrative must not claim an overall cheapest when prices are incomplete."""

    def test_example_narrative_is_blocked(self):
        problems = check(load("report.json"), costs_incomplete())
        self.assertTrue(any("Azure has the lowest" in p for p in problems))
        self.assertTrue(any("cheapest overall" in p for p in problems))
        self.assertTrue(any("Lowest monthly total" in p for p in problems))

    def test_overall_phrasings_blocked(self):
        for s in ["Azure is cheapest.", "Azure is the cheapest option.", "AWS comes out cheapest overall.",
                  "Google Cloud is the least expensive cloud.", "The lowest monthly total is on Azure.",
                  "AWS is 5% above Azure.", "Google Cloud has the highest total."]:
            with self.subTest(s=s):
                self.assertTrue(check(report_with([s]), costs_incomplete()), s)

    def test_allowed_phrasings(self):
        for s in ["Google Cloud has the cheapest storage, saving about $2 a month.",
                  "Cheapest file storage per GB.",
                  "Lowest storage price per GB of the three.",
                  "Like for like on storage and egress, Azure is lowest.",
                  "The clouds are not ranked because AWS web servers are unpriced."]:
            with self.subTest(s=s):
                self.assertEqual(check(report_with([s]), costs_incomplete()), [], s)

    def test_pros_cons_are_checked(self):
        pc = {"azure": {"pros": [{"text": "Lowest monthly total, on demand and committed", "evidence": "x"}], "cons": []}}
        self.assertTrue(check(report_with(pros_cons=pc), costs_incomplete()))

    def test_title_is_not_checked(self):
        r = report_with(["Prices are partial."]); r["title"] = "Which cloud is cheapest overall?"
        self.assertEqual(check(r, costs_incomplete()), [])


class CompleteComparison(unittest.TestCase):
    def test_example_narrative_passes(self):
        self.assertEqual(check(load("report.json"), costs_complete()), [])

    def test_wrong_winner_named(self):
        problems = check(report_with(["AWS is the cheapest option."]), costs_complete())
        self.assertTrue(problems and "costs.json says Azure" in problems[0])

    def test_wrong_winner_in_pros_cons(self):
        pc = {"gcp": {"pros": [{"text": "Lowest monthly total of the three", "evidence": "x"}], "cons": []}}
        self.assertTrue(check(report_with(pros_cons=pc), costs_complete()))

    def test_relative_claims_allowed(self):
        pc = {"aws": {"pros": [{"text": "Second cheapest overall, 5% above Azure", "evidence": "x"}], "cons": []},
              "gcp": {"pros": [], "cons": [{"text": "Highest total cost, about 9% above Azure", "evidence": "x"}]}}
        self.assertEqual(check(report_with(["Azure is cheapest overall."], pc), costs_complete()), [])


@unittest.skipUnless(shutil.which("node"), "node not installed")
class BuildReportUsesSameRules(unittest.TestCase):
    """build_report.js must refuse the same narrative (same rules file)."""

    def setUp(self):
        r = subprocess.run(["node", "-e", "require('docx')"], cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            self.skipTest("docx npm package not installed")
        self.tmp = tempfile.mkdtemp()
        self.diag = os.path.join(self.tmp, "diagrams"); os.makedirs(self.diag)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, report, costs):
        paths = {}
        for name, obj in (("report", report), ("costs", costs)):
            paths[name] = os.path.join(self.tmp, name + ".json")
            with open(paths[name], "w", encoding="utf-8") as f:
                json.dump(obj, f)
        return subprocess.run(["node", os.path.join(ROOT, "scripts", "build_report.js"), paths["report"], paths["costs"],
                               os.path.join(EXAMPLE, "workload.json"), self.diag, os.path.join(self.tmp, "out.docx")],
                              capture_output=True, text=True)

    def test_blocks_incomplete_claim(self):
        r = self.build(load("report.json"), costs_incomplete())
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("narrative check failed", r.stderr)
        self.assertIn("Azure has the lowest", r.stderr)

    def test_builds_complete_example(self):
        r = self.build(load("report.json"), costs_complete())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "out.docx")))


if __name__ == "__main__":
    unittest.main()
