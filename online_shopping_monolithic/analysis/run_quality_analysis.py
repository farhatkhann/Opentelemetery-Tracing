"""
Walks datasets/traces/monolith/{sampling}/{workflow}/run{N}/traces.json
and runs coverage, context-propagation, and journey-reconstruction checks
on every one it finds, then writes:
  - one JSON file per (sampling, workflow, run) with the full detail
    (into --report-dir)
  - one combined summary spreadsheet across everything (quality_summary.xlsx),
    in the same spirit as generate_results.py's performance/volume summary

Usage (run from the analysis/ or scripts/ directory, adjust paths as needed):
    python run_quality_analysis.py \
        --base-dir ../datasets/traces/monolith \
        --inventory ../analysis/static_inventory.json \
        --journeys ../analysis/journeys.json \
        --report-dir ../analysis/quality_reports

Expects the SAME folder layout collect_traces.py already produces:
    {base-dir}/{sampling}/{workflow}/run{N}/traces.json

Where sampling in {off, sample1, sample10, sample100} (matches SAMPLING_RATIOS
in collect_traces.py / SAMPLINGS in generate_results.py -- edit SAMPLINGS
below if your folder names differ).
"""

import argparse
import json
from pathlib import Path
from statistics import mean, stdev

from openpyxl import Workbook

import compute_coverage
import check_context_propagation
import reconstruct_journeys

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


def main():
    ap = argparse.ArgumentParser(description="Run coverage + propagation + journey checks across the full dataset tree")
    ap.add_argument("--base-dir", required=True, help="datasets/traces/monolith")
    ap.add_argument("--inventory", required=True, help="static_inventory.json")
    ap.add_argument("--journeys", required=True, help="journeys.json (from extract_journey_definitions.py)")
    ap.add_argument("--report-dir", required=True, help="Where to write per-run JSON reports")
    ap.add_argument("--summary-out", default=None, help="Combined xlsx path (default: {base-dir}/quality_summary.xlsx)")
    args = ap.parse_args()

    base_dir = Path(args.base_dir)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    journeys = json.load(open(args.journeys))

    # Grouped results for the summary sheet: (sampling, workflow) -> list of per-run metrics
    grouped = {}

    runs = list(find_run_traces(base_dir))
    if not runs:
        print(f"No traces.json files found under {base_dir} matching "
              f"{{sampling}}/{{workflow}}/run{{N}}/traces.json")
        return

    for sampling, workflow, run_num, traces_path in runs:
        print(f"\n=== {sampling} / {workflow} / run{run_num} ===")
        label = f"{sampling}/{workflow}/run{run_num}"

        # ---- coverage ----
        routes, services, repos = compute_coverage.load_inventory(args.inventory)
        op_counts, trace_count, span_count = compute_coverage.stream_trace_operations(traces_path)
        trace_ops = set(op_counts.keys())
        matched_routes = [r for r in routes if r in trace_ops]
        route_coverage_pct = round(100 * len(matched_routes) / len(routes), 2) if routes else 0.0

        # ---- context propagation ----
        prop_report = check_context_propagation.analyze(traces_path)

        # ---- journey reconstruction (only if this workflow has a definition) ----
        journey_report = None
        if workflow in journeys:
            expected_steps = [s["operation"] for s in journeys[workflow]]
            present = [s for s in expected_steps if s in trace_ops]
            missing = [s for s in expected_steps if s not in trace_ops]
            journey_completeness_pct = (
                round(100 * len(present) / len(expected_steps), 2) if expected_steps else 0.0
            )
            journey_report = {
                "expected_step_count": len(expected_steps),
                "steps_present": present,
                "steps_missing": missing,
                "journey_completeness_percent": journey_completeness_pct,
            }
        else:
            print(f"  (no journey definition for '{workflow}' in {args.journeys} -- skipping journey check)")

        # ---- write per-run detail file ----
        detail = {
            "label": label,
            "sampling": sampling,
            "workflow": workflow,
            "run": run_num,
            "trace_count": trace_count,
            "span_count": span_count,
            "route_coverage_percent": route_coverage_pct,
            "matched_routes": matched_routes,
            "context_propagation": prop_report,
            "journey_reconstruction": journey_report,
        }
        out_path = report_dir / f"{sampling}__{workflow}__run{run_num}.json"
        with open(out_path, "w") as f:
            json.dump(detail, f, indent=2)
        print(f"  trace_count={trace_count}  route_coverage={route_coverage_pct}%  "
              f"broken_refs={prop_report['traces_with_broken_references_percent']}%  "
              f"journey_completeness={journey_report['journey_completeness_percent'] if journey_report else 'n/a'}%")

        key = (sampling, workflow)
        grouped.setdefault(key, []).append({
            "trace_count": trace_count,
            "span_count": span_count,
            "route_coverage_percent": route_coverage_pct,
            "broken_refs_percent": prop_report["traces_with_broken_references_percent"],
            "multi_root_percent": prop_report["traces_with_multiple_roots_percent"],
            "journey_completeness_percent": (
                journey_report["journey_completeness_percent"] if journey_report else None
            ),
        })

    # ==========================================================
    # Combined summary spreadsheet
    # ==========================================================
    summary_path = Path(args.summary_out) if args.summary_out else base_dir / "quality_summary.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Quality Summary"
    ws.append([
        "Sampling", "Workflow", "Runs",
        "Avg Trace Count", "SD",
        "Avg Route Coverage %", "SD",
        "Avg Broken-Ref Traces %", "SD",
        "Avg Multi-Root Traces %", "SD",
        "Avg Journey Completeness %", "SD",
    ])

    for (sampling, workflow), rows in sorted(grouped.items(), key=lambda x: (x[0][1], list(SAMPLINGS.keys()).index(x[0][0]))):
        sampling_display = SAMPLINGS.get(sampling, sampling)
        journey_vals = [r["journey_completeness_percent"] for r in rows if r["journey_completeness_percent"] is not None]

        ws.append([
            sampling_display, workflow, len(rows),
            safe_mean([r["trace_count"] for r in rows]), safe_sd([r["trace_count"] for r in rows]),
            safe_mean([r["route_coverage_percent"] for r in rows]), safe_sd([r["route_coverage_percent"] for r in rows]),
            safe_mean([r["broken_refs_percent"] for r in rows]), safe_sd([r["broken_refs_percent"] for r in rows]),
            safe_mean([r["multi_root_percent"] for r in rows]), safe_sd([r["multi_root_percent"] for r in rows]),
            safe_mean(journey_vals) if journey_vals else "n/a", safe_sd(journey_vals) if journey_vals else "n/a",
        ])

    for column_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 3

    wb.save(summary_path)
    print(f"\n{'=' * 60}\nCombined summary saved to {summary_path}\nPer-run detail JSON saved under {report_dir}\n{'=' * 60}")


if __name__ == "__main__":
    main()
