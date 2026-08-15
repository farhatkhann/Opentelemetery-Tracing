#!/usr/bin/env python3
"""
run_quality_analysis.py
--------------------------
Walks datasets/traces/microservices/{sampling}/{workflow}/run{N}/traces.json
and runs coverage, context-propagation, and journey-reconstruction checks
on every one it finds, then writes:
  - one CSV per (sampling, workflow, run) with per-endpoint coverage detail
    (into --report-dir)
  - one combined summary spreadsheet (quality_summary.xlsx) with two sheets:
      "Per Run"      -- one row per (sampling, workflow, run)
      "By Sampling"  -- one row per sampling ratio, with endpoint coverage
                        computed from the UNION of every workflow/run's
                        observed spans at that ratio (this is the number
                        that actually answers "how much coverage does this
                        sampling ratio give me system-wide" -- a single
                        workflow's own traces can never reach 100% coverage
                        against the FULL inventory, since no one workflow
                        calls every endpoint in the app).

This is the CSV/trace_utils-based version of this script, matching
compute_coverage.py, check_context_propagation.py, reconstruct_journeys.py,
and aggregate_coverage_by_sampling.py as currently written. It reads
static_inventory.csv (extract_static_inventory_java.py) and
journey_definitions.csv (extract_journey_definitions.py) -- NOT the older
static_inventory.json / journeys.json shape.

Usage:
    python run_quality_analysis.py \
        --base-dir ../datasets/traces/microservices \
        --inventory static_inventory.csv \
        --journeys journey_definitions.csv \
        --report-dir quality_reports

Expects the folder layout collect_traces.py already produces:
    {base-dir}/{sampling}/{workflow}/run{N}/traces.json

Where sampling is one of the keys in SAMPLINGS below -- edit if your
folder names differ.
"""
import argparse
import os
import sys
from pathlib import Path
from statistics import mean, stdev

from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compute_coverage import load_inventory, build_observed_index
from check_context_propagation import analyze_trace, FANOUT_BY_ROOT_ROUTE
from reconstruct_journeys import load_journey_defs, index_root_spans, reconstruct
from trace_utils import load_traces, normalize_route

SAMPLINGS = {
    "off": "Off",
    "sample1": "1%",
    "sample10": "10%",
    "sample100": "100%",
}


def safe_mean(values):
    return round(mean(values), 2) if values else 0


def safe_sd(values):
    return round(stdev(values), 2) if len(values) > 1 else 0


def find_run_traces(base_dir: Path):
    """
    Yields (sampling_folder, workflow_name, run_number, traces_path) for
    every traces.json found under base_dir, in the
    {sampling}/{workflow}/run{N}/traces.json layout.
    """
    for sampling_dir in sorted(base_dir.iterdir()):
        if not sampling_dir.is_dir() or sampling_dir.name not in SAMPLINGS:
            continue
        for workflow_dir in sorted(sampling_dir.iterdir()):
            if not workflow_dir.is_dir():
                continue
            for run_dir in sorted(workflow_dir.iterdir()):
                if not run_dir.is_dir() or not run_dir.name.startswith("run"):
                    continue
                traces_path = run_dir / "traces.json"
                if traces_path.exists():
                    run_num = int(run_dir.name.replace("run", ""))
                    yield sampling_dir.name, workflow_dir.name, run_num, traces_path


def coverage_pct_for_index(inventory, observed_index):
    covered = 0
    for entry in inventory:
        key = (entry["service"], entry["http_method"].upper(), entry["route_template_normalized"])
        if observed_index.get(key, 0) > 0:
            covered += 1
    total = len(inventory)
    return (round(100 * covered / total, 2) if total else 0.0), covered, total


def propagation_pct_for_traces(traces_path):
    n_fanout_roots = 0
    n_broken_hops = 0
    n_orphaned = 0
    for trace in load_traces(traces_path):
        findings = analyze_trace(trace)
        n_broken_hops += sum(1 for f in findings if f["issue"] == "broken_fanout")
        n_orphaned += sum(1 for f in findings if f["issue"] == "orphaned_span")
        for s in trace["spans"]:
            if not s["parent_span_id"] and s["service"] and s["http_method"] and s["route_raw"]:
                key = (s["service"], s["http_method"].upper(), normalize_route(s["route_raw"]))
                if key in FANOUT_BY_ROOT_ROUTE:
                    n_fanout_roots += 1
    expected_hops = n_fanout_roots * 2
    pct = round(100.0 * (1 - n_broken_hops / expected_hops), 2) if expected_hops else None
    return pct, n_fanout_roots, n_broken_hops, n_orphaned


def journey_pct_for_workflow(workflow, journeys, traces_path, window_seconds):
    steps = journeys.get(workflow)
    if not steps:
        return None, 0, 0
    roots = index_root_spans(str(traces_path))
    attempts = reconstruct(steps, roots, window_seconds)
    if not attempts:
        return 0.0, 0, 0
    complete = sum(1 for a in attempts if a["complete"])
    return round(100 * complete / len(attempts), 2), len(attempts), complete


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", required=True, help="datasets/traces/microservices")
    ap.add_argument("--inventory", required=True, help="static_inventory.csv")
    ap.add_argument("--journeys", required=True, help="journey_definitions.csv (from extract_journey_definitions.py)")
    ap.add_argument("--report-dir", required=True, help="Where to write per-run CSV detail")
    ap.add_argument("--summary-out", default=None, help="Combined xlsx path (default: {base-dir}/quality_summary.xlsx)")
    ap.add_argument("--window-seconds", type=float, default=5.0,
                     help="Journey-reconstruction time window (passed through to reconstruct_journeys logic)")
    args = ap.parse_args()

    base_dir = Path(args.base_dir)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    inventory = load_inventory(args.inventory)
    journeys = load_journey_defs(args.journeys)

    runs = list(find_run_traces(base_dir))
    if not runs:
        print(f"No traces.json files found under {base_dir} matching "
              f"{{sampling}}/{{workflow}}/run{{N}}/traces.json")
        return

    per_run_rows = []
    # sampling -> merged observed index (union of every workflow/run's spans at that ratio)
    merged_by_sampling = {}

    for sampling, workflow, run_num, traces_path in runs:
        print(f"\n=== {sampling} / {workflow} / run{run_num} ===")

        observed, n_traces, n_spans, seen_services = build_observed_index(str(traces_path))
        coverage_pct, covered, total = coverage_pct_for_index(inventory, observed)

        propagation_pct, n_fanout_roots, n_broken_hops, n_orphaned = propagation_pct_for_traces(str(traces_path))

        journey_pct, journey_attempts, journey_complete = journey_pct_for_workflow(
            workflow, journeys, traces_path, args.window_seconds
        )
        if workflow not in journeys:
            print(f"  (no journey definition for '{workflow}' in {args.journeys} -- skipping journey check)")

        print(f"  trace_count={n_traces}  route_coverage={coverage_pct}%  "
              f"propagation={propagation_pct if propagation_pct is not None else 'n/a'}%  "
              f"journey_completeness={journey_pct if journey_pct is not None else 'n/a'}%")

        per_run_rows.append({
            "sampling": sampling,
            "workflow": workflow,
            "run": run_num,
            "trace_count": n_traces,
            "span_count": n_spans,
            "route_coverage_percent": coverage_pct,
            "endpoints_covered": covered,
            "endpoints_total": total,
            "propagation_success_percent": propagation_pct,
            "fanout_roots_seen": n_fanout_roots,
            "orphaned_spans": n_orphaned,
            "journey_completeness_percent": journey_pct,
            "journey_attempts": journey_attempts,
            "journeys_fully_reconstructed": journey_complete,
        })

        merged = merged_by_sampling.setdefault(sampling, {})
        for key, count in observed.items():
            merged[key] = merged.get(key, 0) + count

    # ==========================================================
    # Combined summary spreadsheet
    # ==========================================================
    summary_path = Path(args.summary_out) if args.summary_out else base_dir / "quality_summary.xlsx"
    wb = Workbook()

    # --- Sheet 1: Per Run ---
    ws1 = wb.active
    ws1.title = "Per Run"
    ws1.append([
        "Sampling", "Workflow", "Run", "Trace Count", "Span Count",
        "Route Coverage %", "Endpoints Covered", "Endpoints Total",
        "Propagation Success %", "Fanout Roots Seen", "Orphaned Spans",
        "Journey Completeness %", "Journey Attempts", "Journeys Fully Reconstructed",
    ])
    for r in sorted(per_run_rows, key=lambda x: (x["workflow"], list(SAMPLINGS.keys()).index(x["sampling"]) if x["sampling"] in SAMPLINGS else 99, x["run"])):
        ws1.append([
            SAMPLINGS.get(r["sampling"], r["sampling"]), r["workflow"], r["run"],
            r["trace_count"], r["span_count"],
            r["route_coverage_percent"], r["endpoints_covered"], r["endpoints_total"],
            r["propagation_success_percent"] if r["propagation_success_percent"] is not None else "n/a",
            r["fanout_roots_seen"], r["orphaned_spans"],
            r["journey_completeness_percent"] if r["journey_completeness_percent"] is not None else "n/a",
            r["journey_attempts"], r["journeys_fully_reconstructed"],
        ])

    # --- Sheet 2: By Sampling (union-based coverage -- the honest system-wide number) ---
    ws2 = wb.create_sheet("By Sampling")
    ws2.append(["Sampling", "Runs Included", "Total Traces (sum)",
                "Union Route Coverage %", "Endpoints Covered", "Endpoints Total",
                "Avg Propagation Success %", "SD",
                "Avg Journey Completeness %", "SD"])
    for sampling in SAMPLINGS:
        if sampling not in merged_by_sampling:
            continue
        rows_here = [r for r in per_run_rows if r["sampling"] == sampling]
        union_pct, union_covered, union_total = coverage_pct_for_index(inventory, merged_by_sampling[sampling])
        prop_vals = [r["propagation_success_percent"] for r in rows_here if r["propagation_success_percent"] is not None]
        journey_vals = [r["journey_completeness_percent"] for r in rows_here if r["journey_completeness_percent"] is not None]
        ws2.append([
            SAMPLINGS.get(sampling, sampling), len(rows_here),
            sum(r["trace_count"] for r in rows_here),
            union_pct, union_covered, union_total,
            safe_mean(prop_vals) if prop_vals else "n/a", safe_sd(prop_vals) if prop_vals else "n/a",
            safe_mean(journey_vals) if journey_vals else "n/a", safe_sd(journey_vals) if journey_vals else "n/a",
        ])

    for ws in (ws1, ws2):
        for column_cells in ws.columns:
            length = max((len(str(c.value)) if c.value is not None else 0) for c in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = length + 3

    wb.save(summary_path)
    print(f"\n{'=' * 60}\nCombined summary saved to {summary_path}\n{'=' * 60}")


if __name__ == "__main__":
    main()