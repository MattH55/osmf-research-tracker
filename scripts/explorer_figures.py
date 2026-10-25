#!/usr/bin/env python3
"""Figures for the Drug Repurposing Explorer manuscript, drawn from
data/explorer-stats.json (produced by scripts/explorer_stats.py) so every figure
is regenerable and matches the tables exactly.

    python scripts/explorer_stats.py && python scripts/explorer_figures.py
Writes manuscript/figures/*.png
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATS = json.loads((ROOT / "data" / "explorer-stats.json").read_text(encoding="utf-8"))
FIG = ROOT / "manuscript" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 8, "axes.spines.top": False, "axes.spines.right": False})

# --- Fig 1: score distribution, showing the U-shape and the two caps ---------
bins = STATS["score"]["bins"]
labels = list(bins.keys())
vals = list(bins.values())
fig, ax = plt.subplots(figsize=(5.0, 2.6))
colors = ["#b8c4cc" if int(k.split("-")[0]) < 40 else "#e08b3c" for k in labels]
ax.bar(range(len(labels)), vals, color=colors, edgecolor="white")
ax.set_xticks(range(len(labels)), labels, rotation=0)
ax.set_xlabel("Evidence score (0-80, binned by 10)")
ax.set_ylabel("Pairs")
ax.set_title(f"Score distribution of {STATS['n_pairs']} condition-agent pairs\n"
             f"median {STATS['score']['median']:.0f} · {STATS['score']['max_at_cap']} pairs at the "
             f"80-point ceiling", fontsize=8.5)
for i, v in enumerate(vals):
    ax.text(i, v + 6, str(v), ha="center", fontsize=7)
fig.tight_layout()
fig.savefig(FIG / "fig1-score-distribution.png", dpi=300)
plt.close(fig)

# --- Fig 2: evidence presence (trial vs literature overlap) -----------------
p = STATS["pairs"]
fig, ax = plt.subplots(figsize=(3.4, 2.6))
parts = ["Trial only", "Both", "Literature only", "Neither"]
sizes = [p["trial_only"], p["with_both"], p["literature_only"],
         STATS["n_pairs"] - p["trial_only"] - p["with_both"] - p["literature_only"]]
w, _, at = ax.pie(sizes, colors=["#4b7f98", "#e08b3c", "#7ba05b", "#d5d9dc"],
                  autopct=lambda x: f"{x:.0f}%", startangle=90,
                  textprops={"fontsize": 7}, wedgeprops={"edgecolor": "white"})
ax.legend(w, [f"{s} ({n})" for s, n in zip(parts, sizes)], fontsize=6.5,
          loc="center left", bbox_to_anchor=(0.95, 0.5), frameon=False)
ax.set_title("Evidence type per pair", fontsize=8.5)
fig.tight_layout()
fig.savefig(FIG / "fig2-evidence-presence.png", dpi=300, bbox_inches="tight")
plt.close(fig)

# --- Fig 3: coverage by category (pairs vs conditions) ----------------------
cat = STATS["by_category"]
names = [k if len(k) < 26 else k[:24] + "..." for k in cat]
pairs_ = [v["pairs"] for v in cat.values()]
conds_ = [v["conditions"] for v in cat.values()]
y = range(len(names))
fig, ax = plt.subplots(figsize=(5.2, 3.0))
ax.barh([i + 0.2 for i in y], pairs_, height=0.38, color="#4b7f98", label="Pairs in index")
ax.barh([i - 0.2 for i in y], conds_, height=0.38, color="#c3ccd2", label="Conditions tracked")
for i, (a, b) in enumerate(zip(pairs_, conds_)):
    ax.text(a + 8, i + 0.2, str(a), va="center", fontsize=6.5)
    ax.text(b + 8, i - 0.2, str(b), va="center", fontsize=6.5, color="#5b6a72")
ax.set_yticks(list(y), names)
ax.invert_yaxis()
ax.set_xlabel("Count")
ax.legend(fontsize=7, frameon=False)
ax.set_title("Where the index is dense: pairs versus conditions by category", fontsize=8.5)
ax.set_xlim(0, max(pairs_) * 1.16)
fig.tight_layout()
fig.savefig(FIG / "fig3-category-coverage.png", dpi=300)
plt.close(fig)

# --- Fig 4: pipeline funnel + 25-agent cap ---------------------------------
f = STATS["funnel"]
fig, ax = plt.subplots(figsize=(5.2, 2.4))
stages = ["Therapeutic\ncandidates logged", "Pairs with trial\nor literature",
          "Pairs with BOTH\ntrial and literature"]
nums = [f["candidates_logged"], STATS["n_pairs"], p["with_both"]]
bars = ax.barh(range(3), nums, color=["#c3ccd2", "#4b7f98", "#e08b3c"], edgecolor="white")
for i, n in enumerate(nums):
    ax.text(n + f["candidates_logged"] * 0.01, i, f"{n:,}  "
            f"({100 * n / f['candidates_logged']:.1f}% of candidates)", va="center", fontsize=7)
ax.set_yticks(range(3), stages, fontsize=7)
ax.invert_yaxis()
ax.set_xscale("log")
ax.set_xlim(100, f["candidates_logged"] * 1.5)
ax.set_xlabel("Count (log scale)")
ax.set_title(f"From candidate list to evidence-backed pairs; chronic-disease conditions are "
             f"capped\nat {STATS['integrity']['max_rows_chronic']} enriched agents per condition",
             fontsize=8.5)
fig.tight_layout()
fig.savefig(FIG / "fig4-funnel.png", dpi=300)
plt.close(fig)

print("Wrote figures to", FIG)
for png in sorted(FIG.glob("*.png")):
    print(" ", png.name, round(png.stat().st_size / 1024, 1), "KB")
