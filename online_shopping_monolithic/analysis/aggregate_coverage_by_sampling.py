"""
Computes the coverage metric that actually answers "how much of the app's
route surface does this sampling ratio capture?": for a given sampling
ratio, union the observed operationNames across EVERY workflow's every run,
then compare that union against the full static inventory.

This is different from (and more meaningful than) averaging per-workflow
coverage numbers -- a single k6 workflow only ever exercises a subset of
your app's routes, so per-workflow coverage is capped well below 100% even
with perfect tracing. Aggregating across all workflows first removes that
artifact.

Writes both:
  - a JSON file with full detail (matched/missing routes, per-workflow hits)
  - an Excel workbook (by default saved into --base-dir, alongside
    generate_results.py's grocery_app_monolithic_results.xlsx and
    run_quality_analysis.py's quality_summary.xlsx) with three sheets:
      1. Summary       -- one row per sampling ratio: coverage %, matched/
                           missing route counts, total traces/spans
      2. Route Matrix  -- one row per route, one column per sampling ratio,
                           Yes/No whether that route was seen at that ratio
      3. Per-Workflow Hits -- one row per (workflow, route) pair actually
                           observed, so you can see which workflow is
                           responsible for covering which route

Usage:
    python aggregate_coverage_by_sampling.py \
        --base-dir ../datasets/traces/monolith \
        --inventory static_inventory.json \
        --out aggregate_coverage.json
    # Excel defaults to {base-dir}/aggregate_coverage_by_sampling.xlsx
    # Pass --excel-out to override.
"""

import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

import compute_coverage

SAMPLINGS = ["off", "sample1", "sample10", "sample100"]
SAMPLING_LABELS = {"off": "Off", "sample1": "1%", "sample10": "10%", "sample100": "100%"}


def find_traces_for_sampling(base_dir: Path, sampling: str):
    sampling_dir = base_dir / sampling
    if not sampling_dir.exists():
        return []
    paths = []
    for workflow_dir in sorted(sampling_dir.iterdir()):
        if not workflow_dir.is_dir():
            continue
        for run_dir in sorted(workflow_dir.iterdir()):
            traces_path = run_dir / "traces.json"
            if traces_path.exists():
                paths.append((workflow_dir.name, run_dir.name, traces_path))
    return paths


def main():
    ap = argparse.ArgumentParser(description="Aggregate route coverage across all workflows, per sampling ratio")
    ap.add_argument("--base-dir", required=True)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--out", default="aggregate_coverage.json")
    ap.add_argument("--excel-out", default=None,
                     help="Default: {base-dir}/aggregate_coverage_by_sampling.xlsx")
    args = ap.parse_args()

    base_dir = Path(args.base_dir)
    routes, services, repos = compute_coverage.load_inventory(args.inventory)

    results = {}

    for sampling in SAMPLINGS:
        entries = find_traces_for_sampling(base_dir, sampling)
        if not entries:
            print(f"{sampling}: no traces.json files found, skipping")
            continue

        union_ops = set()
        total_traces = 0
        total_spans = 0
        per_workflow_ops = {}

        for workflow, run, traces_path in entries:
            op_counts, trace_count, span_count = compute_coverage.stream_trace_operations(traces_path)
            union_ops |= set(op_counts.keys())
            total_traces += trace_count
            total_spans += span_count
            per_workflow_ops.setdefault(workflow, set()).update(op_counts.keys())

        matched = sorted(r for r in routes if r in union_ops)
        missing = sorted(r for r in routes if r not in union_ops)
        coverage_pct = round(100 * len(matched) / len(routes), 2) if routes else 0.0

        # Which workflow(s) are responsible for each missing route never being hit anywhere?
        # (helps you tell "sampling dropped it" apart from "no workflow exercises this route at all")
        per_workflow_route_hits = {
            wf: sorted(r for r in routes if r in ops)
            for wf, ops in per_workflow_ops.items()
        }

        results[sampling] = {
            "runs_included": [(wf, run) for wf, run, _ in entries],
            "total_traces": total_traces,
            "total_spans": total_spans,
            "route_coverage_percent": coverage_pct,
            "matched_routes": matched,
            "missing_routes": missing,
            "per_workflow_route_hits": per_workflow_route_hits,
        }

        print(f"{sampling}: {coverage_pct}% ({len(matched)}/{len(routes)} routes) "
              f"across {len(entries)} workflow-run(s), {total_traces} traces")

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved JSON detail to {args.out}")

    excel_path = Path(args.excel_out) if args.excel_out else base_dir / "aggregate_coverage_by_sampling.xlsx"
    write_excel(results, routes, excel_path)
    print(f"Saved Excel summary to {excel_path}")

    # Quick sanity note if 'off' has any coverage or higher ratios don't dominate lower ones
    if "off" in results and results["off"]["route_coverage_percent"] > 0:
        print("\nNOTE: 'off' sampling shows nonzero coverage -- check whether tracing "
              "was actually disabled for that capture, or spans are being emitted "
              "regardless of the sampler setting.")


def autosize_columns(ws):
    for column_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = min(length + 3, 60)


def write_excel(results, routes, excel_path: Path):
    wb = Workbook()
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    yes_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    no_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    def style_header(ws, row=1):
        for cell in ws[row]:
            cell.font = header_font
            cell.fill = header_fill

    # ---- Sheet 1: Summary ----
    ws = wb.active
    ws.title = "Summary"
    ws.append([
        "Sampling Ratio", "Total Traces", "Total Spans",
        "Routes Matched", "Routes Missing", "Total Routes",
        "Route Coverage %",
    ])
    for sampling in SAMPLINGS:
        if sampling not in results:
            continue
        r = results[sampling]
        ws.append([
            SAMPLING_LABELS.get(sampling, sampling),
            r["total_traces"],
            r["total_spans"],
            len(r["matched_routes"]),
            len(r["missing_routes"]),
            len(r["matched_routes"]) + len(r["missing_routes"]),
            r["route_coverage_percent"],
        ])
    style_header(ws)
    autosize_columns(ws)

    # ---- Sheet 2: Route Matrix (route x sampling ratio) ----
    ws2 = wb.create_sheet("Route Matrix")
    present_samplings = [s for s in SAMPLINGS if s in results]
    ws2.append(["Route"] + [SAMPLING_LABELS.get(s, s) for s in present_samplings])
    for route in routes:
        row = [route]
        for sampling in present_samplings:
            hit = route in results[sampling]["matched_routes"]
            row.append("Yes" if hit else "No")
        ws2.append(row)
    style_header(ws2)
    for row in ws2.iter_rows(min_row=2, min_col=2):
        for cell in row:
            cell.fill = yes_fill if cell.value == "Yes" else no_fill
    autosize_columns(ws2)

    # ---- Sheet 3: Per-Workflow Route Hits ----
    ws3 = wb.create_sheet("Per-Workflow Hits")
    ws3.append(["Sampling Ratio", "Workflow", "Route Hit"])
    for sampling in present_samplings:
        for workflow, hit_routes in sorted(results[sampling]["per_workflow_route_hits"].items()):
            for route in hit_routes:
                ws3.append([SAMPLING_LABELS.get(sampling, sampling), workflow, route])
    style_header(ws3)
    autosize_columns(ws3)

    wb.save(excel_path)


if __name__ == "__main__":
    main()