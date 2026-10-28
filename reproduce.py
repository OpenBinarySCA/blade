#!/usr/bin/env python3
"""
BLADE — offline reproduction of the ISSTA 2026 paper's tables and figure.

This script regenerates the quantitative results reported in the paper directly
from the *shipped precomputed detection results* (per-binary JSON reports) and the
benchmark ground truth. It is:

  * OFFLINE   — no internet access required.
  * LLM-FREE  — it never calls a language model. Detection was already run; this
                script only recomputes precision/recall/F1 and the analysis tables.
  * DB-FREE   — it reads JSON files only; no Postgres/Redis/MinIO needed.
  * SELF-CONTAINED — depends only on the Python standard library (matplotlib is
                used *optionally* to render the Top-N figure as a PNG).

Matching between a detection result and the ground truth is done by binary SHA-256,
so the raw benchmark binaries are NOT needed to reproduce the metrics.

The output follows the paper's structure:

  Setup  — Table 2  Dataset distribution
  RQ1    — Table 3  Detection performance  + verification exclusion + error analysis
  RQ2    — Table 4  Ablation               + Figure 10 (Top-N sensitivity)
  RQ3    — Table 5  Generalization on the proprietary in-vehicle dataset

USAGE
  python3 reproduce.py                  # reduced scope: the headline tables (< 1 min)
  python3 reproduce.py --scope full     # full scope: + Top-N figure, exclusion, errors
  python3 reproduce.py --only table3    # print just one table/figure and exit
  python3 reproduce.py --scope full --out results/   # also write JSON summary + figure PNG

See REPRODUCE.md.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "benchmarks"
CONAN = DATA / "conan_bench"
CAR = DATA / "car_bench"
RES = CONAN / "results"

# --- Data sources (paths relative to the repo root) -------------------------- #
CONAN_BENCH = CONAN / "conan_benchmark.json"      # CONAN ground truth (3,403 binaries)

# (label, model_id, evaluation_report.json) for the RQ1 main results table (Table 3).
BLADE_MODELS = [
    ("BLADE-G5",   "gpt-5",        RES / "gpt-5/evaluation_report.json"),
    ("BLADE-G5m",  "gpt-5-mini",   RES / "gpt-5-mini/evaluation_report.json"),
    ("BLADE-G4.1", "gpt-4.1",      RES / "gpt-4.1/evaluation_report.json"),
    ("BLADE-OSS",  "gpt-oss-120b", RES / "gpt-oss-120b/evaluation_report.json"),
]
CAR_G5      = CAR / "results/gpt-5/evaluation_report.json"
# Verification ablations (RQ2 / Table 4)
ABL_NOEVID  = RES / "wo_structured_evidence/evaluation_report.json"
ABL_NOCOT   = RES / "wo_category_guided_verification/evaluation_report.json"
# Top-N: retrieval-only sweep without LLM verification (model-independent).
# Feeds Figure 10 and the Table 4 "w/o Verification" row.
TOPN        = RES / "retrieval_only/topn_analysis.json"
EXCL        = RES / "gpt-5/exclusion_stats.json"
FAIL        = RES / "gpt-5/failure_analysis.json"
BASELINE    = RES / "baselines/baseline_results.json"

CONFIG_ORDER = ["gcc+x86_64", "clang+x86_64", "gcc+arm"]

# ----------------------------------------------------------------------------- #
# Helpers
# ----------------------------------------------------------------------------- #
def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def require(path):
    if not Path(path).exists():
        sys.exit(f"[ERROR] required data file is missing:\n  {path}\n"
                 f"Make sure you are running from the repo root and the precomputed "
                 f"results under data/benchmarks/ are present.")
    return path


def prf(tp, fp, fn):
    p = round(tp / (tp + fp) * 100, 2) if (tp + fp) else 0.0
    r = round(tp / (tp + fn) * 100, 2) if (tp + fn) else 0.0
    f = round(2 * p * r / (p + r), 2) if (p + r) else 0.0
    return p, r, f


def parse_config(notes: str) -> str:
    """Derive the compile configuration (compiler+arch) from a test case's notes,
    so the by-config splits line up with Tables 2 and 3."""
    if not notes:
        return "unknown"
    n = notes.lower()
    m = re.search(r"compile_config:\s*(\S+)", n)
    if m:
        cc = m.group(1)
        arch = "arm" if cc.startswith(("arm", "armv")) else ("x86_64" if "x86_64" in cc else "unknown")
        comp = "clang" if "clang" in cc else ("gcc" if "gcc" in cc else "unknown")
        return f"{comp}+{arch}"
    arch = "arm" if re.search(r"\barm\b|armv\d", n) else ("x86_64" if "x86_64" in n else "unknown")
    comp = "clang" if "clang" in n else ("gcc" if "gcc" in n else "unknown")
    return f"{comp}+{arch}"


def hash_to_config(benchmark):
    m = {}
    for tc in benchmark["test_cases"]:
        b = tc["test_binary"]
        m[b["sha256"]] = parse_config(b.get("notes", ""))
    return m


def report_by_config(report_path, h2c):
    """Aggregate per-binary tp/fp/fn from a shipped evaluation_report.json, split by config."""
    rep = load(report_path)
    agg = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "n": 0})
    for rc in rep["results_check"]:
        cfg = h2c.get(rc.get("binary_hash"), "unknown")
        for key, dst in (("overall", "overall"), (cfg, cfg)):
            agg[dst]["tp"] += rc.get("tp_count", 0)
            agg[dst]["fp"] += rc.get("fp_count", 0)
            agg[dst]["fn"] += rc.get("fn_count", 0)
            agg[dst]["n"] += 1
    return agg, rep["summary"]["effectiveness"]


def hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ----------------------------------------------------------------------------- #
# Setup — Table 2
# ----------------------------------------------------------------------------- #
def table2(out):
    """Table 2 (tab:dataset_distribution) — dataset distribution (re-derived from the CONAN ground truth)."""
    require(CONAN_BENCH)
    bench = load(CONAN_BENCH)
    cfg = defaultdict(lambda: {"bin": 0, "tpl": set(), "reuse": 0})
    all_tpl, all_hash, reuse = set(), set(), 0
    for tc in bench["test_cases"]:
        b, libs = tc["test_binary"], tc["reused_libraries"]
        c = parse_config(b.get("notes", ""))
        cfg[c]["bin"] += 1
        cfg[c]["reuse"] += len(libs)
        for lib in libs:
            cfg[c]["tpl"].add(lib["name"]); all_tpl.add(lib["name"])
        all_hash.add(b["sha256"]); reuse += len(libs)
    hr("SETUP · TABLE 2  Dataset distribution")
    print(f"{'Configuration':<16}{'Binaries':>10}{'TPLs':>8}{'Reuse Rel.':>12}")
    print("-" * 46)
    for c in CONFIG_ORDER:
        s = cfg[c]
        print(f"{c:<16}{s['bin']:>10}{len(s['tpl']):>8}{s['reuse']:>12}")
    print("-" * 46)
    print(f"{'Total (dedup)':<16}{len(all_hash):>10}{len(all_tpl):>8}{reuse:>12}")
    out["table2"] = {"binaries": len(all_hash), "tpls": len(all_tpl), "reuse_relations": reuse,
                     "by_config": {c: {"binaries": cfg[c]["bin"], "tpls": len(cfg[c]["tpl"]),
                                       "reuse": cfg[c]["reuse"]} for c in CONFIG_ORDER}}


# ----------------------------------------------------------------------------- #
# RQ1 — Effectiveness
# ----------------------------------------------------------------------------- #
def table3(out):
    """Table 3 (tab:main_results) — detection performance: BLADE rows (re-derived) + baselines (shipped)."""
    require(CONAN_BENCH)
    h2c = hash_to_config(load(CONAN_BENCH))
    hr("RQ1 · TABLE 3  Detection performance on CONAN  (Overall + per compile config; P / R / F1)")
    cols = ["Overall"] + CONFIG_ORDER
    head = f"{'Method':<12}" + "".join(f"{c:>22}" for c in cols)
    print(head); print("-" * len(head))
    out["table3"] = {"blade": {}, "baseline": {}}
    for label, model, path in BLADE_MODELS:
        if not Path(path).exists():
            print(f"{label:<12}  (report missing: {path})"); continue
        agg, summ = report_by_config(path, h2c)
        cells, row = [], f"{label:<12}"
        for c in cols:
            key = "overall" if c == "Overall" else c
            s = agg[key]
            p, r, f = prf(s["tp"], s["fp"], s["fn"])
            row += f"{f'{p:.1f}/{r:.1f}/{f:.1f}':>22}"
            cells.append({"config": c, "tp": s["tp"], "fp": s["fp"], "fn": s["fn"],
                          "precision": p, "recall": r, "f1": f})
        print(row)
        out["table3"]["blade"][label] = cells
    # baselines (precomputed)
    if Path(BASELINE).exists():
        b = load(BASELINE)
        print("-" * len(head))
        for tool in ["CT1", "CT2", "BAT", "OssPolice", "B2SFinder", "BinaryAI"]:
            if tool not in b:
                continue
            row = f"{tool:<12}"
            rowdata = []
            for c in cols:
                key = "overall" if c == "Overall" else c
                m = b[tool].get(key)
                if m:
                    cell = f"{m['precision']:.1f}/{m['recall']:.1f}/{m['f1']:.1f}"
                    row += f"{cell:>22}"
                    rowdata.append({"config": c, **{k: m[k] for k in ("precision", "recall", "f1")}})
                else:
                    row += f"{'-':>22}"
            print(row)
            out["table3"]["baseline"][tool] = rowdata
    print("\n(cells are Precision/Recall/F1; BLADE rows re-derived from per-binary results,"
          "\n baseline rows are the precomputed values shipped in baseline_results.json)")


def exclusion(out):
    """RQ1 verification-stage exclusion analysis (C1–C5 false-positive taxonomy)."""
    require(EXCL)
    x = load(EXCL)
    hr("RQ1 · Verification-stage exclusion")
    print(f"candidates retrieved : {x['total_retrieved']}")
    print(f"excluded by verifier : {x['total_excluded']}  ({x['exclusion_rate']}%)")
    print(f"confirmed            : {x['total_confirmed']}  (TP={x['total_tp']}, FP={x['total_fp']})")
    print("\nFalse-positive type breakdown (C1–C5):")
    for c, s in x["fp_type_stats"].items():
        print(f"  {c}: {s['count']:>6}  ({s['ratio']}%)")
    out["exclusion"] = x


def failures(out):
    """RQ1 error analysis: FN (retrieval-failure vs verification-exclusion) and FP."""
    require(FAIL)
    s = load(FAIL).get("summary", {})
    hr("RQ1 · Error analysis (false negatives / false positives)")
    print(f"total false negatives : {s.get('total_fn')}")
    print(f"  due to retrieval failure   : {s.get('fn_retrieval_failure')}"
          f"  ({s.get('fn_retrieval_ratio')}%)")
    print(f"  due to verification exclude: {s.get('fn_verification_exclusion')}"
          f"  ({s.get('fn_verification_ratio')}%)")
    print(f"total false positives : {s.get('total_fp')}")
    out["failures"] = {k: s.get(k) for k in
                       ("total_fn", "fn_retrieval_failure", "fn_verification_exclusion", "total_fp")}


# ----------------------------------------------------------------------------- #
# RQ2 — Ablation
# ----------------------------------------------------------------------------- #
def table4(out):
    """Table 4 (tab:ablation) — verification ablation (GPT-5-mini)."""
    h2c = hash_to_config(load(require(CONAN_BENCH)))
    hr("RQ2 · TABLE 4  Ablation study on CONAN (GPT-5-mini; P / R / F1)")
    rows = []
    # baseline (full BLADE)
    _, summ = report_by_config(BLADE_MODELS[1][2], h2c)
    rows.append(("BLADE (full)", summ["precision"], summ["recall"], summ["f1_score"]))
    # w/o Verification = retrieval-only Top-N at n=10
    if Path(TOPN).exists():
        tn = load(TOPN)
        e10 = next((e for e in tn["top_n_metrics"] if e.get("top_n") == 10), None)
        if e10:
            rows.append(("w/o Verification", e10["precision"], e10["recall"], e10["f1"]))
    # w/o Structured Evidence
    if Path(ABL_NOEVID).exists():
        e = load(ABL_NOEVID)["summary"]["effectiveness"]
        rows.append(("w/o Struct. Evidence", e["precision"], e["recall"], e["f1_score"]))
    # w/o Category-Guided Verification
    if Path(ABL_NOCOT).exists():
        e = load(ABL_NOCOT)["summary"]["effectiveness"]
        rows.append(("w/o Category-Guided Verif.", e["precision"], e["recall"], e["f1_score"]))
    print(f"{'Variant':<22}{'Precision':>11}{'Recall':>9}{'F1':>9}")
    print("-" * 51)
    for name, p, r, f in rows:
        print(f"{name:<22}{p:>11}{r:>9}{f:>9}")
    out["table4"] = [{"variant": n, "precision": p, "recall": r, "f1": f} for n, p, r, f in rows]


def figure10(out):
    """Figure 10 (fig:topn_sensitivity) — Top-N retrieval sensitivity (and optional PNG)."""
    require(TOPN)
    tn = load(TOPN)
    hr("RQ2 · FIGURE 10  Top-N retrieval-only sensitivity")
    print(f"{'Top-N':>6}{'Precision':>11}{'Recall':>9}{'F1':>9}")
    print("-" * 35)
    pts = []
    for e in tn["top_n_metrics"]:
        n = e["top_n"]
        if n in (1, 2, 3, 5, 10, 20, 50, 100):
            print(f"{n:>6}{e['precision']:>11}{e['recall']:>9}{e['f1']:>9}")
        pts.append((n, e["precision"], e["recall"]))
    out["figure10"] = {"n10": next((e for e in tn["top_n_metrics"] if e["top_n"] == 10), None)}
    if out.get("_out_dir"):
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            ns = [p[0] for p in pts]; ps = [p[1] for p in pts]; rs = [p[2] for p in pts]
            plt.figure(figsize=(5, 3.2))
            plt.plot(ns, rs, "-o", ms=3, label="Recall")
            plt.plot(ns, ps, "-s", ms=3, label="Precision")
            plt.xlabel("Top-N"); plt.ylabel("%"); plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
            fig = Path(out["_out_dir"]) / "figure10_topn.png"
            plt.savefig(fig, dpi=150)
            print(f"\n[figure written] {fig}")
        except Exception as ex:  # matplotlib optional
            print(f"\n[figure skipped — matplotlib unavailable: {ex}]")


# ----------------------------------------------------------------------------- #
# RQ3 — Generalization
# ----------------------------------------------------------------------------- #
def table5(out):
    """Table 5 (tab:proprietary) — generalization on the proprietary in-vehicle dataset (BLADE row)."""
    hr("RQ3 · TABLE 5  Generalization on proprietary in-vehicle dataset (CAR, 277 binaries; P / R / F1)")
    if Path(CAR_G5).exists():
        e = load(CAR_G5)["summary"]["effectiveness"]
        print(f"{'BLADE (GPT-5)':<22}{e['precision']:>11}{e['recall']:>9}{e['f1_score']:>9}")
        out["table5"] = {"blade": {"precision": e["precision"], "recall": e["recall"], "f1": e["f1_score"]}}


# Map for --only: print a single table/figure block (by the name used in the README).
ONLY_BLOCKS = {
    "table2":    lambda out: table2(out),
    "table3":    lambda out: table3(out),
    "table4":    lambda out: table4(out),
    "table5":    lambda out: table5(out),
    "figure10":  lambda out: figure10(out),
    "exclusion": lambda out: exclusion(out),
    "errors":    lambda out: failures(out),
}


# ----------------------------------------------------------------------------- #
# Main
# ----------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(
        description="Offline reproduction of BLADE's paper results, organized by RQ.")
    ap.add_argument("--scope", choices=["reduced", "full"], default="reduced",
                    help="reduced = headline tables only (Setup + RQ1/RQ2/RQ3; paper Tables 2-5); "
                         "full = also Figure 10 and the RQ1 exclusion/error analyses")
    ap.add_argument("--out", metavar="DIR", default=None,
                    help="write machine-readable repro_summary.json (+ figure PNG) to DIR")
    ap.add_argument("--only", choices=sorted(ONLY_BLOCKS), metavar="BLOCK", default=None,
                    help="print just one block and exit (" + ", ".join(sorted(ONLY_BLOCKS)) + ")")
    args = ap.parse_args()

    out = {}
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        out["_out_dir"] = args.out

    print("BLADE — offline reproduction of the ISSTA 2026 results (no LLM, no network, no database)")
    print(f"repo root: {ROOT}")

    if args.only:
        ONLY_BLOCKS[args.only](out)
        return

    full = args.scope == "full"

    # Setup
    table2(out)
    # RQ1 — Effectiveness
    table3(out)
    if full:
        exclusion(out)
        failures(out)
    # RQ2 — Ablation
    table4(out)
    if full:
        figure10(out)
    # RQ3 — Generalization
    table5(out)

    if args.out:
        out.pop("_out_dir", None)
        p = Path(args.out) / "repro_summary.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"[written] {p}")


if __name__ == "__main__":
    main()
