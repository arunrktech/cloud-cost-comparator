#!/usr/bin/env python3
"""Check that report.json does not make overall cost claims the numbers do not support.

Usage: python narrative_check.py report.json costs.json
Exit code 0 when clean, 1 with a list of problems otherwise.

Rules (patterns live in narrative_rules.json, shared with build_report.js):
  * Incomplete comparison (costs.json "complete": false): no sentence may claim an overall
    ranking (cheapest overall, lowest monthly total, 9% above Azure, Azure is cheapest, ...).
    Sentences that say "like for like" are allowed, because they refer to the comparable subset.
  * Complete comparison: a winner claim must name the actual cheapest cloud. In pros_cons the
    subject is the cloud the point belongs to; elsewhere it is the cloud named in the sentence.
Per component claims ("cheapest storage per GB", "lowest storage price") are not affected.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {"aws": "AWS", "gcp": "Google Cloud", "azure": "Azure"}


def load_rules():
    with open(os.path.join(HERE, "narrative_rules.json"), encoding="utf-8") as f:
        r = json.load(f)
    return {"overall": [re.compile(p, re.I) for p in r["overall_claims"]],
            "not_winner": re.compile(r["not_a_winner_claim"], re.I),
            "named": re.compile(r["named_winner"], re.I),
            "exempt": [e.lower() for e in r["exempt"]],
            "alias": r["cloud_aliases"]}


def walk(node, path="report"):
    """Yield (path, subject_cloud, text) for every string in report.json."""
    if isinstance(node, str):
        yield path, None, node
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in ("title", "subtitle", "author", "date") and path == "report":
                continue
            if path == "report" and k == "pros_cons" and isinstance(v, dict):
                for cloud, d in v.items():
                    for p, _, t in walk(d, f"report.pros_cons.{cloud}"):
                        yield p, cloud, t
                continue
            yield from walk(v, f"{path}.{k}")


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


def check(report, costs, rules=None):
    rules = rules or load_rules()
    complete = bool(costs.get("complete", True))
    cheapest = (costs.get("variance", {}).get("ondemand", {}) or {}).get("cheapest")
    problems = []
    for path, subject, text in walk(report):
        for s in sentences(text):
            low = s.lower()
            if any(e in low for e in rules["exempt"]):
                continue
            hit = next((m.group(0) for p in rules["overall"] for m in [p.search(s)] if m), None)
            if not hit:
                continue
            if not complete:
                problems.append(f"{path}: overall cost claim '{hit}' but the comparison is incomplete (unpriced items). "
                                f"Rewrite without ranking the clouds, or say 'like for like'. Sentence: \"{s}\"")
                continue
            if rules["not_winner"].search(s):
                continue  # 'second cheapest', '9% above Azure', 'highest total' are not winner claims
            named = rules["named"].search(s)
            claimed = rules["alias"].get(named.group(1).lower()) if named else subject
            if claimed and cheapest and claimed != cheapest:
                problems.append(f"{path}: claims {NAMES.get(claimed, claimed)} is cheapest ('{hit}') but costs.json says "
                                f"{NAMES[cheapest]}. Sentence: \"{s}\"")
    return problems


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python narrative_check.py report.json costs.json")
    data = []
    for path, what in ((sys.argv[1], "report"), (sys.argv[2], "costs")):
        try:
            with open(path, encoding="utf-8") as f:
                data.append(json.load(f))
        except FileNotFoundError:
            sys.exit(f"ERROR: {what} file not found: {path}")
        except json.JSONDecodeError as e:
            sys.exit(f"ERROR: {what} file is not valid JSON ({path}, line {e.lineno}): {e.msg}")
    problems = check(*data)
    if problems:
        print("NARRATIVE CHECK FAILED:\n  " + "\n  ".join(problems))
        sys.exit(1)
    print("Narrative check passed.")


if __name__ == "__main__":
    main()
