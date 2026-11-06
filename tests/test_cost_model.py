"""Tests for scripts/cost_model.py. Run from the repo root: python -m unittest discover tests"""
import copy, json, os, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import cost_model  # noqa: E402

EXAMPLE = os.path.join(ROOT, "assets", "example")


def load(name):
    with open(os.path.join(EXAMPLE, name), encoding="utf-8") as f:
        return json.load(f)


class CompleteExample(unittest.TestCase):
    def test_example_totals_and_cheapest(self):
        res = cost_model.compute(load("prices.json"), load("workload.json"))
        v = res["variance"]["ondemand"]
        self.assertTrue(res["complete"])
        self.assertEqual(v["cheapest"], "azure")
        self.assertEqual(v["totals"], {"aws": 167.67, "gcp": 173.46, "azure": 159.26})
        self.assertEqual(res["variance"]["commit"]["cheapest"], "azure")
        self.assertEqual(res["warnings"], [])


class UnpricedItems(unittest.TestCase):
    """Reviewer bug 1: an unpriced line must never make a cloud look cheapest."""

    def setUp(self):
        self.prices = load("prices.json")
        self.workload = load("workload.json")
        aws = self.prices["clouds"]["aws"]
        aws[:] = [l for l in aws if l["component"] != "web"]
        aws.append({"component": "web", "item": "EC2 m7i.large", "source": "unpriced", "note": "price not found"})

    def test_no_overall_cheapest_when_incomplete(self):
        self.assertEqual(cost_model.validate(self.prices, self.workload), [])
        res = cost_model.compute(self.prices, self.workload)
        v = res["variance"]["ondemand"]
        self.assertFalse(res["complete"])
        self.assertIsNone(v["cheapest"])
        self.assertIsNone(v["vs_cheapest"])
        self.assertIsNone(res["variance"]["commit"]["cheapest"])
        self.assertEqual(v["incomplete_clouds"], ["aws"])
        self.assertTrue(res["warnings"] and "No overall cheapest" in res["warnings"][0])

    def test_like_for_like_excludes_gap_component_on_every_cloud(self):
        res = cost_model.compute(self.prices, self.workload)
        lf = res["variance"]["ondemand"]["like_for_like"]
        self.assertEqual(lf["excluded_components"], ["web"])
        self.assertEqual(lf["components"], ["files", "egress"])
        # files + egress only: AWS 11.50 + 9.00, GCP 9.31 + 22.35, Azure 10.40 + 8.70
        self.assertEqual(lf["totals"], {"aws": 20.5, "gcp": 31.66, "azure": 19.1})
        self.assertEqual(lf["cheapest"], "azure")

    def test_gap_component_is_not_ranked(self):
        res = cost_model.compute(self.prices, self.workload)
        web = next(r for r in res["components"] if r["component"] == "web")
        self.assertFalse(web["comparable"])
        self.assertEqual(web["gaps_on"], ["aws"])
        self.assertIsNone(web["ondemand_cheapest"])
        self.assertIsNone(web["ondemand_spread_usd"])
        self.assertNotIn("web", [d["component"] for d in res["top_variance_drivers"]])

    def test_partially_priced_component_is_not_comparable(self):
        # A cloud with a priced line AND an unpriced line for the same component is still incomplete.
        p = load("prices.json")
        p["clouds"]["gcp"].append({"component": "web", "item": "OS licence", "source": "unpriced", "note": "not found"})
        res = cost_model.compute(p, load("workload.json"))
        self.assertIsNone(res["variance"]["ondemand"]["cheapest"])
        self.assertEqual(res["variance"]["ondemand"]["like_for_like"]["excluded_components"], ["web"])

    def test_component_missing_on_a_cloud_without_workload(self):
        p = load("prices.json")
        p["clouds"]["azure"] = [l for l in p["clouds"]["azure"] if l["component"] != "files"]
        res = cost_model.compute(p, None)
        self.assertIsNone(res["variance"]["ondemand"]["cheapest"])
        self.assertIn("files", res["variance"]["ondemand"]["like_for_like"]["excluded_components"])


class OfficialUrls(unittest.TestCase):
    """Reviewer bug 2: the URL check must match the real hostname, not a substring."""

    def check(self, url):
        p = load("prices.json")
        p["clouds"]["aws"][0]["url"] = url
        return cost_model.validate(p, None)

    def test_rejects_lookalikes_and_other_products(self):
        for bad in ["https://docs.google.com/spreadsheets/d/abc/edit",
                    "https://notgoogle.com.evil.example/pricing",
                    "https://cloud.google.com.evil.example/x",
                    "https://evil.example/?ref=aws.amazon.com",
                    "https://www.amazon.com/dp/B000",
                    "https://my-bucket.s3.amazonaws.com/prices.csv",
                    "https://aws.amazon.com@evil.example/x",
                    "http://aws.amazon.com/ec2/pricing/",
                    "aws.amazon.com/ec2/pricing/",
                    "ftp://pricing.us-east-1.amazonaws.com/x"]:
            with self.subTest(url=bad):
                errs = self.check(bad)
                self.assertTrue(any("url" in e for e in errs), f"accepted {bad}")

    def test_accepts_official_hosts(self):
        for good in ["https://aws.amazon.com/ec2/pricing/on-demand/",
                     "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv",
                     "https://cloud.google.com/storage/pricing",
                     "https://docs.cloud.google.com/bigquery/docs/introduction",
                     "https://prices.azure.com/api/retail/prices",
                     "https://azure.microsoft.com/en-us/pricing/details/storage/blobs/",
                     "https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices",
                     "HTTPS://AWS.AMAZON.COM/s3/pricing/"]:
            with self.subTest(url=good):
                self.assertEqual(self.check(good), [])


class FriendlyErrors(unittest.TestCase):
    """Reviewer small bug: wrong paths and bad JSON give a clear message, not a traceback."""

    def run_script(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "cost_model.py"), *args],
                              capture_output=True, text=True)

    def test_missing_prices_file(self):
        r = self.run_script("no/such/prices.json", "--out", os.devnull)
        self.assertEqual(r.returncode, 1)
        self.assertIn("prices file not found", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_missing_workload_file(self):
        r = self.run_script(os.path.join(EXAMPLE, "prices.json"), "--workload", "nope.json", "--out", os.devnull)
        self.assertIn("workload file not found", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_invalid_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        try:
            r = self.run_script(f.name, "--out", os.devnull)
            self.assertIn("not valid JSON", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        finally:
            os.unlink(f.name)

    def test_unwritable_output(self):
        r = self.run_script(os.path.join(EXAMPLE, "prices.json"), "--out", os.path.join("no", "such", "dir", "costs.json"))
        self.assertIn("cannot write output file", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
