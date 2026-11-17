#!/usr/bin/env python3
"""Re-score scripts/nondrug/outcomes.py against the hand-labelled samples in data/nondrug/outcome_rule_checks.json.

Reports agreement (hand label among the rule's domains), precision (labelled outcomes that were right)
and how many outcomes the rules left unclassified. Add new samples to the JSON as the rules evolve;
only a sample labelled BEFORE a rule change measures out-of-sample accuracy.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from outcomes import domains_for_outcome  # noqa: E402

doc = json.loads((HERE.parents[1] / "data" / "nondrug" / "outcome_rule_checks.json").read_text(encoding="utf-8"))
for s in doc["samples"]:
    agree = labelled = right = 0
    for it in s["items"]:
        got = domains_for_outcome(it["measure"]) or ["unclassified"]
        agree += it["hand_label"] in got
        if got != ["unclassified"]:
            labelled += 1
            right += it["hand_label"] in got
    n = len(s["items"])
    print(f"{agree}/{n} agree; {right}/{labelled} of rule-labelled outcomes correct; {n - labelled} unclassified  [{s['note']}]")
