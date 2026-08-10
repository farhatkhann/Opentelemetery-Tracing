# """
# Walks datasets/traces/monolith/{sampling}/{workflow}/run{N}/traces.json
# and runs coverage, context-propagation, and journey-reconstruction checks
# on every one it finds, then writes:
#   - one JSON file per (sampling, workflow, run) with the full detail
#     (into --report-dir)
#   - one combined summary spreadsheet across everything (quality_summary.xlsx),
#     in the same spirit as generate_results.py's performance/volume summary

# Usage (run from the analysis/ or scripts/ directory, adjust paths as needed):
#     python run_quality_analysis.py \
#         --base-dir ../datasets/traces/monolith \
#         --inventory ../analysis/static_inventory.json \
#         --journeys ../analysis/journeys.json \
#         --report-dir ../analysis/quality_reports

# Expects the SAME folder layout collect_traces.py already produces:
#     {base-dir}/{sampling}/{workflow}/run{N}/traces.json

# Where sampling in {off, sample1, sample10, sample100} (matches SAMPLING_RATIOS
# in collect_traces.py / SAMPLINGS in generate_results.py -- edit SAMPLINGS
# below if your folder names differ).
# """

# import argparse
# import json
# from pathlib import Path
# from statistics import mean, stdev

# from openpyxl import Workbook

# import compute_coverage
# import check_context_propagation
# import reconstruct_journeys

# SAMPLINGS = {
#     "off": "Off",
#     "sample1": "1%",
#     "sample10": "10%",
#     "sample100": "100%",
# }


# def safe_mean(values):
#     return round(mean(values), 2) if values else 0


# def safe_sd(values):
#     return round(stdev(values), 2) if len(values) > 1 else 0


# def find_run_traces(base_dir: Path):
#     """
#     Yields (sampling_folder, workflow_name, run_number, traces_path) for
#     every traces.json found under base_dir, in the
#     {sampling}/{workflow}/run{N}/traces.json layout.
#     """
#     for sampling_dir in sorted(base_dir.iterdir()):
#         if not sampling_dir.is_dir() or sampling_dir.name not in SAMPLINGS:
#             continue
#         for workflow_dir in sorted(sampling_dir.iterdir()):
#             if not workflow_dir.is_dir():
#                 continue
#             for run_dir in sorted(workflow_dir.iterdir()):
#                 if not run_dir.is_dir() or not run_dir.name.startswith("run"):
#                     continue
#                 traces_path = run_dir / "traces.json"
#                 if traces_path.exists():
#                     run_num = int(run_dir.name.replace("run", ""))
#                     yield sampling_dir.name, workflow_dir.name, run_num, traces_path


# def main():
#     ap = argparse.ArgumentParser(description="Run coverage + propagation + journey checks across the full dataset tree")
#     ap.add_argument("--base-dir", required=True, help="datasets/traces/monolith")
#     ap.add_argument("--inventory", required=True, help="static_inventory.json")
#     ap.add_argument("--journeys", required=True, help="journeys.json (from extract_journey_definitions.py)")
#     ap.add_argument("--report-dir", required=True, help="Where to write per-run JSON reports")
#     ap.add_argument("--summary-out", default=None, help="Combined xlsx path (default: {base-dir}/quality_summary.xlsx)")
#     args = ap.parse_args()

#     base_dir = Path(args.base_dir)
#     report_dir = Path(args.report_dir)
#     report_dir.mkdir(parents=True, exist_ok=True)

#     journeys = json.load(open(args.journeys))

#     # Grouped results for the summary sheet: (sampling, workflow) -> list of per-run metrics
#     grouped = {}

#     runs = list(find_run_traces(base_dir))
#     if not runs:
#         print(f"No traces.json files found under {base_dir} matching "
#               f"{{sampling}}/{{workflow}}/run{{N}}/traces.json")
#         return

#     for sampling, workflow, run_num, traces_path in runs:
#         print(f"\n=== {sampling} / {workflow} / run{run_num} ===")
#         label = f"{sampling}/{workflow}/run{run_num}"

#         # ---- coverage ----
#         routes, services, repos = compute_coverage.load_inventory(args.inventory)
#         op_counts, trace_count, span_count = compute_coverage.stream_trace_operations(traces_path)
#         trace_ops = set(op_counts.keys())
#         matched_routes = [r for r in routes if r in trace_ops]
#         route_coverage_pct = round(100 * len(matched_routes) / len(routes), 2) if routes else 0.0

#         # ---- context propagation ----
#         prop_report = check_context_propagation.analyze(traces_path)

#         # ---- journey reconstruction (only if this workflow has a definition) ----
#         journey_report = None
#         if workflow in journeys:
#             expected_steps = [s["operation"] for s in journeys[workflow]]
#             present = [s for s in expected_steps if s in trace_ops]
#             missing = [s for s in expected_steps if s not in trace_ops]
#             journey_completeness_pct = (
#                 round(100 * len(present) / len(expected_steps), 2) if expected_steps else 0.0
#             )
#             journey_report = {
#                 "expected_step_count": len(expected_steps),
#                 "steps_present": present,
#                 "steps_missing": missing,
#                 "journey_completeness_percent": journey_completeness_pct,
#             }
#         else:
#             print(f"  (no journey definition for '{workflow}' in {args.journeys} -- skipping journey check)")

#         # ---- write per-run detail file ----
#         detail = {
#             "label": label,
#             "sampling": sampling,
#             "workflow": workflow,
#             "run": run_num,
#             "trace_count": trace_count,
#             "span_count": span_count,
#             "route_coverage_percent": route_coverage_pct,
#             "matched_routes": matched_routes,
#             "context_propagation": prop_report,
#             "journey_reconstruction": journey_report,
#         }
#         out_path = report_dir / f"{sampling}__{workflow}__run{run_num}.json"
#         with open(out_path, "w") as f:
#             json.dump(detail, f, indent=2)
#         print(f"  trace_count={trace_count}  route_coverage={route_coverage_pct}%  "
#               f"broken_refs={prop_report['traces_with_broken_references_percent']}%  "
#               f"journey_completeness={journey_report['journey_completeness_percent'] if journey_report else 'n/a'}%")

#         key = (sampling, workflow)
#         grouped.setdefault(key, []).append({
#             "trace_count": trace_count,
#             "span_count": span_count,
#             "route_coverage_percent": route_coverage_pct,
#             "broken_refs_percent": prop_report["traces_with_broken_references_percent"],
#             "multi_root_percent": prop_report["traces_with_multiple_roots_percent"],
#             "journey_completeness_percent": (
#                 journey_report["journey_completeness_percent"] if journey_report else None
#             ),
#         })

#     # ==========================================================
#     # Combined summary spreadsheet
#     # ==========================================================
#     summary_path = Path(args.summary_out) if args.summary_out else base_dir / "quality_summary.xlsx"

#     wb = Workbook()
#     ws = wb.active
#     ws.title = "Quality Summary"
#     ws.append([
#         "Sampling", "Workflow", "Runs",
#         "Avg Trace Count", "SD",
#         "Avg Route Coverage %", "SD",
#         "Avg Broken-Ref Traces %", "SD",
#         "Avg Multi-Root Traces %", "SD",
#         "Avg Journey Completeness %", "SD",
#     ])

#     for (sampling, workflow), rows in sorted(grouped.items(), key=lambda x: (x[0][1], list(SAMPLINGS.keys()).index(x[0][0]))):
#         sampling_display = SAMPLINGS.get(sampling, sampling)
#         journey_vals = [r["journey_completeness_percent"] for r in rows if r["journey_completeness_percent"] is not None]

#         ws.append([
#             sampling_display, workflow, len(rows),
#             safe_mean([r["trace_count"] for r in rows]), safe_sd([r["trace_count"] for r in rows]),
#             safe_mean([r["route_coverage_percent"] for r in rows]), safe_sd([r["route_coverage_percent"] for r in rows]),
#             safe_mean([r["broken_refs_percent"] for r in rows]), safe_sd([r["broken_refs_percent"] for r in rows]),
#             safe_mean([r["multi_root_percent"] for r in rows]), safe_sd([r["multi_root_percent"] for r in rows]),
#             safe_mean(journey_vals) if journey_vals else "n/a", safe_sd(journey_vals) if journey_vals else "n/a",
#         ])

#     for column_cells in ws.columns:
#         length = max((len(str(c.value)) if c.value is not None else 0) for c in column_cells)
#         ws.column_dimensions[column_cells[0].column_letter].width = length + 3

#     wb.save(summary_path)
#     print(f"\n{'=' * 60}\nCombined summary saved to {summary_path}\nPer-run detail JSON saved under {report_dir}\n{'=' * 60}")


# if __name__ == "__main__":
#     main()

"""
Run trace-quality analysis across the full dataset tree.

Checks:
1. Route coverage
2. Context propagation
3. Journey completeness

Supports both:
- Monolithic inventories
- Microservices inventories

For microservices, route matching is performed using:

    (Jaeger serviceName, operationName)

instead of only:

    operationName

This is important because multiple microservices can expose the
same route, such as GET / or PUT /cart.
"""

import argparse
import json
from pathlib import Path
from statistics import mean, stdev

from openpyxl import Workbook

import compute_coverage
import check_context_propagation

import service_map as service_map_mod
# ------------------------------------------------------------
# Sampling display names
# ------------------------------------------------------------

SAMPLINGS = {
    "off": "Off",
    "sample1": "1%",
    "sample10": "10%",
    "sample100": "100%",
}


# ------------------------------------------------------------
# Statistics helpers
# ------------------------------------------------------------

def safe_mean(values):
    """
    Return mean rounded to 2 decimal places.

    If there are no values, return 0.
    """
    return round(mean(values), 2) if values else 0


def safe_sd(values):
    """
    Return standard deviation rounded to 2 decimal places.

    If there is only one value, return 0.
    """
    return round(stdev(values), 2) if len(values) > 1 else 0


# ------------------------------------------------------------
# Find traces
# ------------------------------------------------------------

def find_run_traces(base_dir: Path):
    """
    Find every traces.json under:

        {base-dir}/{sampling}/{workflow}/run{N}/traces.json

    Yields:

        sampling_folder,
        workflow_name,
        run_number,
        traces_path
    """

    if not base_dir.exists():
        print(f"ERROR: Base directory does not exist: {base_dir}")
        return

    for sampling_dir in sorted(base_dir.iterdir()):

        if not sampling_dir.is_dir():
            continue

        if sampling_dir.name not in SAMPLINGS:
            continue

        for workflow_dir in sorted(sampling_dir.iterdir()):

            if not workflow_dir.is_dir():
                continue

            for run_dir in sorted(workflow_dir.iterdir()):

                if not run_dir.is_dir():
                    continue

                if not run_dir.name.startswith("run"):
                    continue

                traces_path = run_dir / "traces.json"

                if traces_path.exists():

                    run_num = int(
                        run_dir.name.replace("run", "")
                    )

                    yield (
                        sampling_dir.name,
                        workflow_dir.name,
                        run_num,
                        traces_path,
                    )


# ------------------------------------------------------------
# Route coverage
# ------------------------------------------------------------

def calculate_route_coverage(
    inventory_path,
    op_counts,
    service_op_counts
):
    """
    Calculate route coverage.

    Monolith:
        Match operationName directly.

    Microservices:
        Match:

            (inventory service, operation)
                against
            (Jaeger serviceName, operation)

        using the service mapping from compute_coverage.py.

    Returns:

        route_coverage_percent
        matched_routes
        missing_routes
        unexpected_routes
        is_microservices
    """

    routes, services, repos = compute_coverage.load_inventory(
        inventory_path
    )

    if not routes:

        return {
            "route_coverage_percent": 0.0,
            "matched_routes": [],
            "missing_routes": [],
            "unexpected_routes": [],
            "is_microservices": False,
        }

    # --------------------------------------------------------
    # Determine whether inventory is microservices inventory
    # --------------------------------------------------------

    is_microservices = isinstance(routes[0], tuple)

    # --------------------------------------------------------
    # Microservices
    # --------------------------------------------------------

    if is_microservices:

        # Load the same service mapping used by
        # compute_coverage.py.
        # service_map = compute_coverage.load_service_map(None)
        service_map = service_map_mod.load_service_map(None)

        observed_pairs = set(
            service_op_counts.keys()
        )

        matched_routes = []
        missing_routes = []

        for inventory_service, route_name in routes:

            jaeger_service = service_map.get(
                inventory_service
            )

            display = (
                f"[{inventory_service}] {route_name}"
            )

            if (
                jaeger_service
                and
                (jaeger_service, route_name)
                in observed_pairs
            ):

                matched_routes.append(display)

            else:

                missing_routes.append(display)

        matched_routes.sort()
        missing_routes.sort()

        # ----------------------------------------------------
        # Find unexpected route operations
        # ----------------------------------------------------

        inventory_pairs = {
            (
                service_map.get(inventory_service),
                route_name,
            )
            for inventory_service, route_name in routes
        }

        unexpected_routes = sorted(
            f"[{service}] {operation}"
            for service, operation in observed_pairs
            if (
                compute_coverage.ROUTE_RE.match(operation)
                and
                (service, operation)
                not in inventory_pairs
            )
        )

    # --------------------------------------------------------
    # Monolith
    # --------------------------------------------------------

    else:

        trace_ops = set(op_counts.keys())

        matched_routes = sorted(
            route
            for route in routes
            if route in trace_ops
        )

        missing_routes = sorted(
            route
            for route in routes
            if route not in trace_ops
        )

        trace_route_ops = {
            operation
            for operation in trace_ops
            if compute_coverage.ROUTE_RE.match(operation)
        }

        unexpected_routes = sorted(
            trace_route_ops - set(routes)
        )

    # --------------------------------------------------------
    # Coverage percentage
    # --------------------------------------------------------

    route_coverage_pct = (
        round(
            100 * len(matched_routes) / len(routes),
            2
        )
        if routes
        else 0.0
    )

    return {
        "route_coverage_percent": route_coverage_pct,
        "matched_routes": matched_routes,
        "missing_routes": missing_routes,
        "unexpected_routes": unexpected_routes,
        "is_microservices": is_microservices,
    }


# ------------------------------------------------------------
# Journey completeness
# ------------------------------------------------------------

def calculate_journey_completeness(
    workflow,
    journeys,
    op_counts
):
    """
    Calculate journey completeness.

    journeys.json currently stores only operation names,
    for example:

        GET /
        PUT /cart
        GET /cart

    Therefore journey matching remains operation-level.

    For microservices route coverage, service-aware matching is
    used separately.

    Returns None if no journey definition exists.
    """

    if workflow not in journeys:

        return None

    expected_steps = [
        step["operation"]
        for step in journeys[workflow]
    ]

    trace_ops = set(op_counts.keys())

    present = [
        operation
        for operation in expected_steps
        if operation in trace_ops
    ]

    missing = [
        operation
        for operation in expected_steps
        if operation not in trace_ops
    ]

    journey_completeness_pct = (
        round(
            100 * len(present) / len(expected_steps),
            2
        )
        if expected_steps
        else 0.0
    )

    return {
        "expected_step_count": len(expected_steps),
        "steps_present": present,
        "steps_missing": missing,
        "journey_completeness_percent": (
            journey_completeness_pct
        ),
    }


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    ap = argparse.ArgumentParser(
        description=(
            "Run coverage + propagation + journey "
            "checks across the full dataset tree"
        )
    )

    ap.add_argument(
        "--base-dir",
        required=True,
        help="datasets/traces/monolith or datasets/traces/microservices"
    )

    ap.add_argument(
        "--inventory",
        required=True,
        help="static_inventory.json"
    )

    ap.add_argument(
        "--journeys",
        required=True,
        help="journeys.json"
    )

    ap.add_argument(
        "--report-dir",
        required=True,
        help="Directory for per-run JSON reports"
    )

    ap.add_argument(
        "--summary-out",
        default=None,
        help=(
            "Combined XLSX path. "
            "Default: {base-dir}/quality_summary.xlsx"
        )
    )

    args = ap.parse_args()

    # --------------------------------------------------------
    # Paths
    # --------------------------------------------------------

    base_dir = Path(args.base_dir)
    inventory_path = Path(args.inventory)
    journeys_path = Path(args.journeys)
    report_dir = Path(args.report_dir)

    # --------------------------------------------------------
    # Validate paths
    # --------------------------------------------------------

    if not base_dir.exists():

        print(
            f"ERROR: Base directory does not exist:\n"
            f"  {base_dir}"
        )

        return

    if not inventory_path.exists():

        print(
            f"ERROR: Inventory file does not exist:\n"
            f"  {inventory_path}"
        )

        return

    if not journeys_path.exists():

        print(
            f"ERROR: Journeys file does not exist:\n"
            f"  {journeys_path}"
        )

        return

    # --------------------------------------------------------
    # Create report directory
    # --------------------------------------------------------

    report_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load journeys
    # --------------------------------------------------------

    with open(
        journeys_path,
        "r",
        encoding="utf-8"
    ) as f:

        journeys = json.load(f)

    # --------------------------------------------------------
    # Grouped results for Excel
    #
    # Key:
    #
    #     (sampling, workflow)
    #
    # Value:
    #
    #     list of per-run results
    # --------------------------------------------------------

    grouped = {}

    # --------------------------------------------------------
    # Find all traces
    # --------------------------------------------------------

    runs = list(
        find_run_traces(base_dir)
    )

    if not runs:

        print(
            f"No traces.json files found under:\n"
            f"{base_dir}\n\n"
            f"Expected structure:\n"
            f"{{sampling}}/{{workflow}}/run{{N}}/traces.json"
        )

        return

    print("=" * 70)
    print("TRACE QUALITY ANALYSIS")
    print("=" * 70)

    print(f"Base directory : {base_dir}")
    print(f"Inventory      : {inventory_path}")
    print(f"Journeys       : {journeys_path}")
    print(f"Reports        : {report_dir}")
    print(f"Runs found     : {len(runs)}")

    # --------------------------------------------------------
    # Process every run
    # --------------------------------------------------------

    for (
        sampling,
        workflow,
        run_num,
        traces_path
    ) in runs:

        print()
        print("=" * 70)

        print(
            f"=== {sampling} / "
            f"{workflow} / "
            f"run{run_num} ==="
        )

        print("=" * 70)

        label = (
            f"{sampling}/{workflow}/run{run_num}"
        )

        # ====================================================
        # Load inventory
        # ====================================================

        routes, services, repos = (
            compute_coverage.load_inventory(
                inventory_path
            )
        )

        # ====================================================
        # Read trace operations
        #
        # IMPORTANT:
        #
        # stream_trace_operations() returns FOUR values:
        #
        #   1. op_counts
        #   2. trace_count
        #   3. span_count
        #   4. service_op_counts
        #
        # This fixes the previous:
        #
        # ValueError:
        # too many values to unpack
        # ====================================================

        (
            op_counts,
            trace_count,
            span_count,
            service_op_counts
        ) = compute_coverage.stream_trace_operations(
            traces_path
        )

        # ====================================================
        # Route coverage
        # ====================================================

        coverage = calculate_route_coverage(
            inventory_path,
            op_counts,
            service_op_counts
        )

        route_coverage_pct = (
            coverage["route_coverage_percent"]
        )

        matched_routes = (
            coverage["matched_routes"]
        )

        missing_routes = (
            coverage["missing_routes"]
        )

        unexpected_routes = (
            coverage["unexpected_routes"]
        )

        is_microservices = (
            coverage["is_microservices"]
        )

        # ====================================================
        # Context propagation
        # ====================================================

        prop_report = (
            check_context_propagation.analyze(
                traces_path
            )
        )

        # ====================================================
        # Journey reconstruction
        # ====================================================

        journey_report = (
            calculate_journey_completeness(
                workflow,
                journeys,
                op_counts
            )
        )

        # ====================================================
        # Console output
        # ====================================================

        print(
            f"  Trace count          : {trace_count}"
        )

        print(
            f"  Span count           : {span_count}"
        )

        print(
            f"  Inventory mode       : "
            f"{'microservices' if is_microservices else 'monolith'}"
        )

        print(
            f"  Static routes        : {len(routes)}"
        )

        print(
            f"  Matched routes       : "
            f"{len(matched_routes)}"
        )

        print(
            f"  Missing routes       : "
            f"{len(missing_routes)}"
        )

        print(
            f"  Route coverage       : "
            f"{route_coverage_pct}%"
        )

        print(
            f"  Broken references   : "
            f"{prop_report['traces_with_broken_references_percent']}%"
        )

        print(
            f"  Multiple roots       : "
            f"{prop_report['traces_with_multiple_roots_percent']}%"
        )

        if journey_report:

            print(
                f"  Journey completeness: "
                f"{journey_report['journey_completeness_percent']}%"
            )

        else:

            print(
                f"  Journey completeness: n/a"
            )

        # ====================================================
        # Per-run detail report
        # ====================================================

        detail = {

            "label": label,

            "sampling": sampling,

            "workflow": workflow,

            "run": run_num,

            "microservices_mode": is_microservices,

            "trace_count": trace_count,

            "span_count": span_count,

            "route_coverage_percent": (
                route_coverage_pct
            ),

            "static_route_count": len(routes),

            "matched_route_count": (
                len(matched_routes)
            ),

            "missing_route_count": (
                len(missing_routes)
            ),

            "matched_routes": matched_routes,

            "missing_routes": missing_routes,

            "unexpected_route_operations": (
                unexpected_routes
            ),

            "context_propagation": prop_report,

            "journey_reconstruction": journey_report,

        }

        # ----------------------------------------------------
        # Save per-run JSON
        # ----------------------------------------------------

        out_path = (
            report_dir
            / f"{sampling}__{workflow}__run{run_num}.json"
        )

        with open(
            out_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                detail,
                f,
                indent=2
            )

        print(
            f"  Report saved         : {out_path}"
        )

        # ====================================================
        # Add to Excel grouping
        # ====================================================

        key = (
            sampling,
            workflow
        )

        grouped.setdefault(
            key,
            []
        ).append(
            {
                "trace_count": trace_count,

                "span_count": span_count,

                "route_coverage_percent": (
                    route_coverage_pct
                ),

                "broken_refs_percent": (
                    prop_report[
                        "traces_with_broken_references_percent"
                    ]
                ),

                "multi_root_percent": (
                    prop_report[
                        "traces_with_multiple_roots_percent"
                    ]
                ),

                "journey_completeness_percent": (
                    journey_report[
                        "journey_completeness_percent"
                    ]
                    if journey_report
                    else None
                ),
            }
        )

    # ========================================================
    # Combined summary spreadsheet
    # ========================================================

    summary_path = (
        Path(args.summary_out)
        if args.summary_out
        else base_dir / "quality_summary.xlsx"
    )

    print()
    print("=" * 70)
    print("Creating combined quality summary")
    print("=" * 70)

    wb = Workbook()

    ws = wb.active

    ws.title = "Quality Summary"

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    ws.append(
        [
            "Sampling",
            "Workflow",
            "Runs",

            "Avg Trace Count",
            "SD",

            "Avg Route Coverage %",
            "SD",

            "Avg Broken-Ref Traces %",
            "SD",

            "Avg Multi-Root Traces %",
            "SD",

            "Avg Journey Completeness %",
            "SD",
        ]
    )

    # --------------------------------------------------------
    # Sort:
    #
    # workflow first
    # sampling order:
    #
    # Off
    # 100%
    # 10%
    # 1%
    #
    # Change SAMPLINGS order if you want a different order.
    # --------------------------------------------------------

    sampling_order = [
        "off",
        "sample100",
        "sample10",
        "sample1",
    ]

    for (
        sampling,
        workflow
    ), rows in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][1],
            (
                sampling_order.index(item[0][0])
                if item[0][0] in sampling_order
                else 999
            ),
        )
    ):

        sampling_display = (
            SAMPLINGS.get(
                sampling,
                sampling
            )
        )

        # ----------------------------------------------------
        # Journey values
        # ----------------------------------------------------

        journey_vals = [
            row["journey_completeness_percent"]
            for row in rows
            if row["journey_completeness_percent"]
            is not None
        ]

        # ----------------------------------------------------
        # Append summary row
        # ----------------------------------------------------

        ws.append(
            [
                sampling_display,

                workflow,

                len(rows),

                # Trace count
                safe_mean(
                    [
                        row["trace_count"]
                        for row in rows
                    ]
                ),

                safe_sd(
                    [
                        row["trace_count"]
                        for row in rows
                    ]
                ),

                # Route coverage
                safe_mean(
                    [
                        row[
                            "route_coverage_percent"
                        ]
                        for row in rows
                    ]
                ),

                safe_sd(
                    [
                        row[
                            "route_coverage_percent"
                        ]
                        for row in rows
                    ]
                ),

                # Broken references
                safe_mean(
                    [
                        row[
                            "broken_refs_percent"
                        ]
                        for row in rows
                    ]
                ),

                safe_sd(
                    [
                        row[
                            "broken_refs_percent"
                        ]
                        for row in rows
                    ]
                ),

                # Multiple roots
                safe_mean(
                    [
                        row[
                            "multi_root_percent"
                        ]
                        for row in rows
                    ]
                ),

                safe_sd(
                    [
                        row[
                            "multi_root_percent"
                        ]
                        for row in rows
                    ]
                ),

                # Journey completeness
                (
                    safe_mean(journey_vals)
                    if journey_vals
                    else "n/a"
                ),

                (
                    safe_sd(journey_vals)
                    if journey_vals
                    else "n/a"
                ),
            ]
        )

    # ========================================================
    # Auto-size Excel columns
    # ========================================================

    for column_cells in ws.columns:

        length = max(
            (
                len(str(cell.value))
                if cell.value is not None
                else 0
            )
            for cell in column_cells
        )

        ws.column_dimensions[
            column_cells[0].column_letter
        ].width = length + 3

    # ========================================================
    # Save Excel
    # ========================================================

    wb.save(summary_path)

    print()
    print("=" * 70)

    print(
        f"Combined summary saved to:\n"
        f"  {summary_path}"
    )

    print(
        f"Per-run JSON reports saved under:\n"
        f"  {report_dir}"
    )

    print("=" * 70)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

if __name__ == "__main__":
    main()