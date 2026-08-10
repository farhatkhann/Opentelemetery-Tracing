# """
# Computes the coverage metric that actually answers "how much of the app's
# route surface does this sampling ratio capture?": for a given sampling
# ratio, union the observed operationNames across EVERY workflow's every run,
# then compare that union against the full static inventory.

# This is different from (and more meaningful than) averaging per-workflow
# coverage numbers -- a single k6 workflow only ever exercises a subset of
# your app's routes, so per-workflow coverage is capped well below 100% even
# with perfect tracing. Aggregating across all workflows first removes that
# artifact.

# Writes both:
#   - a JSON file with full detail (matched/missing routes, per-workflow hits)
#   - an Excel workbook (by default saved into --base-dir, alongside
#     generate_results.py's grocery_app_monolithic_results.xlsx and
#     run_quality_analysis.py's quality_summary.xlsx) with three sheets:
#       1. Summary       -- one row per sampling ratio: coverage %, matched/
#                            missing route counts, total traces/spans
#       2. Route Matrix  -- one row per route, one column per sampling ratio,
#                            Yes/No whether that route was seen at that ratio
#       3. Per-Workflow Hits -- one row per (workflow, route) pair actually
#                            observed, so you can see which workflow is
#                            responsible for covering which route

# Usage:
#     python aggregate_coverage_by_sampling.py \
#         --base-dir ../datasets/traces/monolith \
#         --inventory static_inventory.json \
#         --out aggregate_coverage.json
#     # Excel defaults to {base-dir}/aggregate_coverage_by_sampling.xlsx
#     # Pass --excel-out to override.
# """

# import argparse
# import json
# from pathlib import Path

# from openpyxl import Workbook
# from openpyxl.styles import Font, PatternFill

# import compute_coverage

# SAMPLINGS = ["off", "sample1", "sample10", "sample100"]
# SAMPLING_LABELS = {"off": "Off", "sample1": "1%", "sample10": "10%", "sample100": "100%"}


# def find_traces_for_sampling(base_dir: Path, sampling: str):
#     sampling_dir = base_dir / sampling
#     if not sampling_dir.exists():
#         return []
#     paths = []
#     for workflow_dir in sorted(sampling_dir.iterdir()):
#         if not workflow_dir.is_dir():
#             continue
#         for run_dir in sorted(workflow_dir.iterdir()):
#             traces_path = run_dir / "traces.json"
#             if traces_path.exists():
#                 paths.append((workflow_dir.name, run_dir.name, traces_path))
#     return paths


# def main():
#     ap = argparse.ArgumentParser(description="Aggregate route coverage across all workflows, per sampling ratio")
#     ap.add_argument("--base-dir", required=True)
#     ap.add_argument("--inventory", required=True)
#     ap.add_argument("--out", default="aggregate_coverage.json")
#     ap.add_argument("--excel-out", default=None,
#                      help="Default: {base-dir}/aggregate_coverage_by_sampling.xlsx")
#     args = ap.parse_args()

#     base_dir = Path(args.base_dir)
#     routes, services, repos = compute_coverage.load_inventory(args.inventory)

#     results = {}

#     for sampling in SAMPLINGS:
#         entries = find_traces_for_sampling(base_dir, sampling)
#         if not entries:
#             print(f"{sampling}: no traces.json files found, skipping")
#             continue

#         union_ops = set()
#         total_traces = 0
#         total_spans = 0
#         per_workflow_ops = {}

#         for workflow, run, traces_path in entries:
#             op_counts, trace_count, span_count = compute_coverage.stream_trace_operations(traces_path)
#             union_ops |= set(op_counts.keys())
#             total_traces += trace_count
#             total_spans += span_count
#             per_workflow_ops.setdefault(workflow, set()).update(op_counts.keys())

#         matched = sorted(r for r in routes if r in union_ops)
#         missing = sorted(r for r in routes if r not in union_ops)
#         coverage_pct = round(100 * len(matched) / len(routes), 2) if routes else 0.0

#         # Which workflow(s) are responsible for each missing route never being hit anywhere?
#         # (helps you tell "sampling dropped it" apart from "no workflow exercises this route at all")
#         per_workflow_route_hits = {
#             wf: sorted(r for r in routes if r in ops)
#             for wf, ops in per_workflow_ops.items()
#         }

#         results[sampling] = {
#             "runs_included": [(wf, run) for wf, run, _ in entries],
#             "total_traces": total_traces,
#             "total_spans": total_spans,
#             "route_coverage_percent": coverage_pct,
#             "matched_routes": matched,
#             "missing_routes": missing,
#             "per_workflow_route_hits": per_workflow_route_hits,
#         }

#         print(f"{sampling}: {coverage_pct}% ({len(matched)}/{len(routes)} routes) "
#               f"across {len(entries)} workflow-run(s), {total_traces} traces")

#     with open(args.out, "w") as f:
#         json.dump(results, f, indent=2)
#     print(f"\nSaved JSON detail to {args.out}")

#     excel_path = Path(args.excel_out) if args.excel_out else base_dir / "aggregate_coverage_by_sampling.xlsx"
#     write_excel(results, routes, excel_path)
#     print(f"Saved Excel summary to {excel_path}")

#     # Quick sanity note if 'off' has any coverage or higher ratios don't dominate lower ones
#     if "off" in results and results["off"]["route_coverage_percent"] > 0:
#         print("\nNOTE: 'off' sampling shows nonzero coverage -- check whether tracing "
#               "was actually disabled for that capture, or spans are being emitted "
#               "regardless of the sampler setting.")


# def autosize_columns(ws):
#     for column_cells in ws.columns:
#         length = max((len(str(c.value)) if c.value is not None else 0) for c in column_cells)
#         ws.column_dimensions[column_cells[0].column_letter].width = min(length + 3, 60)


# def write_excel(results, routes, excel_path: Path):
#     wb = Workbook()
#     header_font = Font(bold=True, color="FFFFFF")
#     header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
#     yes_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
#     no_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

#     def style_header(ws, row=1):
#         for cell in ws[row]:
#             cell.font = header_font
#             cell.fill = header_fill

#     # ---- Sheet 1: Summary ----
#     ws = wb.active
#     ws.title = "Summary"
#     ws.append([
#         "Sampling Ratio", "Total Traces", "Total Spans",
#         "Routes Matched", "Routes Missing", "Total Routes",
#         "Route Coverage %",
#     ])
#     for sampling in SAMPLINGS:
#         if sampling not in results:
#             continue
#         r = results[sampling]
#         ws.append([
#             SAMPLING_LABELS.get(sampling, sampling),
#             r["total_traces"],
#             r["total_spans"],
#             len(r["matched_routes"]),
#             len(r["missing_routes"]),
#             len(r["matched_routes"]) + len(r["missing_routes"]),
#             r["route_coverage_percent"],
#         ])
#     style_header(ws)
#     autosize_columns(ws)

#     # ---- Sheet 2: Route Matrix (route x sampling ratio) ----
#     ws2 = wb.create_sheet("Route Matrix")
#     present_samplings = [s for s in SAMPLINGS if s in results]
#     ws2.append(["Route"] + [SAMPLING_LABELS.get(s, s) for s in present_samplings])
#     for route in routes:
#         row = [route]
#         for sampling in present_samplings:
#             hit = route in results[sampling]["matched_routes"]
#             row.append("Yes" if hit else "No")
#         ws2.append(row)
#     style_header(ws2)
#     for row in ws2.iter_rows(min_row=2, min_col=2):
#         for cell in row:
#             cell.fill = yes_fill if cell.value == "Yes" else no_fill
#     autosize_columns(ws2)

#     # ---- Sheet 3: Per-Workflow Route Hits ----
#     ws3 = wb.create_sheet("Per-Workflow Hits")
#     ws3.append(["Sampling Ratio", "Workflow", "Route Hit"])
#     for sampling in present_samplings:
#         for workflow, hit_routes in sorted(results[sampling]["per_workflow_route_hits"].items()):
#             for route in hit_routes:
#                 ws3.append([SAMPLING_LABELS.get(sampling, sampling), workflow, route])
#     style_header(ws3)
#     autosize_columns(ws3)

#     wb.save(excel_path)


# if __name__ == "__main__":
#     main()


import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

import compute_coverage
import service_map as service_map_mod


# ============================================================
# Sampling configuration
# ============================================================

SAMPLINGS = [
    "off",
    "sample100",
    "sample10",
    "sample1",
]

SAMPLING_LABELS = {
    "off": "Off",
    "sample100": "100%",
    "sample10": "10%",
    "sample1": "1%",
}


# ============================================================
# Find traces for a sampling ratio
# ============================================================

def find_traces_for_sampling(base_dir, sampling):
    """
    Find all traces.json files under:

        base_dir/
            sampling/
                workflow/
                    run1/
                        traces.json
                    run2/
                        traces.json
    """

    sampling_dir = Path(base_dir) / sampling

    if not sampling_dir.exists():
        return []

    traces = []

    for workflow_dir in sorted(sampling_dir.iterdir()):

        if not workflow_dir.is_dir():
            continue

        for run_dir in sorted(workflow_dir.iterdir()):

            if not run_dir.is_dir():
                continue

            traces_path = run_dir / "traces.json"

            if traces_path.exists():

                traces.append({
                    "workflow": workflow_dir.name,
                    "run": run_dir.name,
                    "path": traces_path
                })

    return traces


# ============================================================
# Convert route to display format
# ============================================================

def route_to_string(route):
    """
    Convert:

        ("customer", "POST /login")

    into:

        "[customer] POST /login"

    For monolith routes, simply return:

        "GET /"
    """

    if isinstance(route, tuple):
        service, operation = route
        return f"[{service}] {operation}"

    return str(route)


# ============================================================
# Build service-aware routes
# ============================================================

def build_service_routes(service_op_counts, service_map):
    """
    Convert Jaeger service names into the service names used
    by the static inventory.

    Example:

        service_map:

            customer -> customer-service
            products -> products-service
            shopping -> shopping-service

        service_op_counts:

            ("customer-service", "POST /login")

    becomes:

            ("customer", "POST /login")
    """

    reverse_map = {}

    for inventory_service, jaeger_service in service_map.items():

        if jaeger_service:
            reverse_map[jaeger_service] = inventory_service

    observed_routes = set()

    for service_operation in service_op_counts.keys():

        if not isinstance(service_operation, tuple):
            continue

        if len(service_operation) != 2:
            continue

        jaeger_service, operation = service_operation

        inventory_service = reverse_map.get(jaeger_service)

        if inventory_service is not None:

            observed_routes.add(
                (
                    inventory_service,
                    operation
                )
            )

    return observed_routes


# ============================================================
# Apply Excel header formatting
# ============================================================

def format_header(worksheet):
    """
    Make the first row bold.
    """

    for cell in worksheet[1]:
        cell.font = Font(bold=True)


# ============================================================
# Automatically resize Excel columns
# ============================================================

def resize_columns(worksheet):

    for column in worksheet.columns:

        max_length = 0

        for cell in column:

            if cell.value is not None:

                length = len(str(cell.value))

                if length > max_length:
                    max_length = length

        column_letter = column[0].column_letter

        worksheet.column_dimensions[
            column_letter
        ].width = min(max_length + 3, 60)


# ============================================================
# Create Excel report
# ============================================================

def create_excel_report(
    results,
    inventory_routes,
    output_path
):

    workbook = Workbook()

    # ========================================================
    # Summary sheet
    # ========================================================

    summary = workbook.active
    summary.title = "Summary"

    summary.append([
        "Sampling",
        "Workflow-Runs",
        "Total Traces",
        "Total Spans",
        "Matched Routes",
        "Missing Routes",
        "Total Routes",
        "Coverage %"
    ])

    for sampling in SAMPLINGS:

        if sampling not in results:
            continue

        data = results[sampling]

        summary.append([
            data["sampling_label"],
            data["total_workflow_runs"],
            data["total_traces"],
            data["total_spans"],
            data["matched_route_count"],
            data["missing_route_count"],
            data["static_route_count"],
            data["route_coverage_percent"]
        ])

    format_header(summary)
    resize_columns(summary)

    # ========================================================
    # Route Matrix sheet
    # ========================================================

    route_matrix = workbook.create_sheet(
        "Route Matrix"
    )

    present_samplings = [
        sampling
        for sampling in SAMPLINGS
        if sampling in results
    ]

    route_matrix.append(
        ["Route"]
        + [
            SAMPLING_LABELS[sampling]
            for sampling in present_samplings
        ]
    )

    for route in inventory_routes:

        route_string = route_to_string(route)

        row = [route_string]

        for sampling in present_samplings:

            matched_routes = results[sampling][
                "matched_routes"
            ]

            if route_string in matched_routes:
                row.append("Yes")
            else:
                row.append("No")

        route_matrix.append(row)

    format_header(route_matrix)

    yes_fill = PatternFill(
        start_color="C6EFCE",
        end_color="C6EFCE",
        fill_type="solid"
    )

    no_fill = PatternFill(
        start_color="FFC7CE",
        end_color="FFC7CE",
        fill_type="solid"
    )

    for row in route_matrix.iter_rows(
        min_row=2,
        min_col=2
    ):

        for cell in row:

            if cell.value == "Yes":
                cell.fill = yes_fill

            elif cell.value == "No":
                cell.fill = no_fill

    resize_columns(route_matrix)

    # ========================================================
    # Per-Workflow Hits sheet
    # ========================================================

    workflow_sheet = workbook.create_sheet(
        "Per-Workflow Hits"
    )

    workflow_sheet.append([
        "Sampling",
        "Workflow",
        "Matched Route"
    ])

    for sampling in present_samplings:

        workflow_data = results[sampling][
            "per_workflow_route_hits"
        ]

        for workflow in sorted(workflow_data):

            routes = workflow_data[workflow]

            for route in routes:

                workflow_sheet.append([
                    SAMPLING_LABELS[sampling],
                    workflow,
                    route
                ])

    format_header(workflow_sheet)
    resize_columns(workflow_sheet)

    # ========================================================
    # Missing Routes sheet
    # ========================================================

    missing_sheet = workbook.create_sheet(
        "Missing Routes"
    )

    missing_sheet.append([
        "Sampling",
        "Missing Route"
    ])

    for sampling in present_samplings:

        missing_routes = results[sampling][
            "missing_routes"
        ]

        for route in missing_routes:

            missing_sheet.append([
                SAMPLING_LABELS[sampling],
                route
            ])

    format_header(missing_sheet)
    resize_columns(missing_sheet)

    # ========================================================
    # Save workbook
    # ========================================================

    workbook.save(output_path)


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Aggregate route coverage by sampling ratio"
        )
    )

    parser.add_argument(
        "--base-dir",
        required=True,
        help=(
            "Base traces directory, for example "
            "../datasets/traces/microservices"
        )
    )

    parser.add_argument(
        "--inventory",
        required=True,
        help="Path to static_inventory.json"
    )

    parser.add_argument(
        "--out",
        default="aggregate_coverage.json",
        help="Output JSON file"
    )

    parser.add_argument(
        "--excel-out",
        default=None,
        help=(
            "Output Excel file. "
            "If omitted, it is created inside base-dir."
        )
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    inventory_path = Path(args.inventory)
    json_output = Path(args.out)

    # ========================================================
    # Validate paths
    # ========================================================

    if not base_dir.exists():

        print(
            f"ERROR: Base directory does not exist:\n"
            f"{base_dir}"
        )

        return

    if not inventory_path.exists():

        print(
            f"ERROR: Inventory file does not exist:\n"
            f"{inventory_path}"
        )

        return

    # ========================================================
    # Load static inventory
    # ========================================================

    routes, services, repositories = (
        compute_coverage.load_inventory(
            inventory_path
        )
    )

    if not routes:

        print(
            "ERROR: No routes found in inventory."
        )

        return

    # ========================================================
    # Detect inventory type
    # ========================================================

    microservices_mode = isinstance(
        routes[0],
        tuple
    )

    print()
    print("=" * 70)
    print("AGGREGATE COVERAGE BY SAMPLING")
    print("=" * 70)

    print(
        f"Base directory : {base_dir}"
    )

    print(
        f"Inventory      : {inventory_path}"
    )

    print(
        "Architecture   : "
        + (
            "microservices"
            if microservices_mode
            else "monolith"
        )
    )

    print(
        f"Static routes  : {len(routes)}"
    )

    print()

    # ========================================================
    # Load service map
    # ========================================================

    service_map = {}

    if microservices_mode:

        service_map = (
            service_map_mod.load_service_map(
                None
            )
        )

        print("Service mapping:")

        for inventory_service in sorted(
            service_map
        ):

            print(
                f"  {inventory_service} -> "
                f"{service_map[inventory_service]}"
            )

        print()

    # ========================================================
    # Store final results
    # ========================================================

    results = {}

    # ========================================================
    # Process each sampling
    # ========================================================

    for sampling in SAMPLINGS:

        print("-" * 70)

        print(
            f"Sampling: "
            f"{SAMPLING_LABELS[sampling]}"
        )

        trace_files = (
            find_traces_for_sampling(
                base_dir,
                sampling
            )
        )

        if not trace_files:

            print(
                "No trace files found."
            )

            continue

        # ----------------------------------------------------
        # Union of operations
        # ----------------------------------------------------

        all_operations = set()

        # ----------------------------------------------------
        # Union of service + operation pairs
        # ----------------------------------------------------

        all_service_operations = set()

        # ----------------------------------------------------
        # Per workflow
        # ----------------------------------------------------

        workflow_operations = {}

        # ----------------------------------------------------
        # Totals
        # ----------------------------------------------------

        total_traces = 0
        total_spans = 0

        # ====================================================
        # Process every workflow/run
        # ====================================================

        for item in trace_files:

            workflow = item["workflow"]
            run = item["run"]
            traces_path = item["path"]

            print(
                f"  Processing: "
                f"{workflow}/{run}"
            )

            # IMPORTANT:
            #
            # Current compute_coverage.py returns FOUR values.
            #
            (
                op_counts,
                trace_count,
                span_count,
                service_op_counts
            ) = (
                compute_coverage.stream_trace_operations(
                    traces_path
                )
            )

            total_traces += trace_count
            total_spans += span_count

            # ------------------------------------------------
            # Monolith
            # ------------------------------------------------

            if not microservices_mode:

                operations = set(
                    op_counts.keys()
                )

                all_operations.update(
                    operations
                )

                if workflow not in workflow_operations:

                    workflow_operations[
                        workflow
                    ] = set()

                workflow_operations[
                    workflow
                ].update(operations)

            # ------------------------------------------------
            # Microservices
            # ------------------------------------------------

            else:

                service_operations = (
                    build_service_routes(
                        service_op_counts,
                        service_map
                    )
                )

                all_service_operations.update(
                    service_operations
                )

                if workflow not in workflow_operations:

                    workflow_operations[
                        workflow
                    ] = set()

                workflow_operations[
                    workflow
                ].update(
                    service_operations
                )

        # ====================================================
        # Calculate route coverage
        # ====================================================

        matched_routes = []
        missing_routes = []

        for route in routes:

            if microservices_mode:

                found = (
                    route
                    in all_service_operations
                )

            else:

                found = (
                    route
                    in all_operations
                )

            if found:
                matched_routes.append(
                    route_to_string(route)
                )
            else:
                missing_routes.append(
                    route_to_string(route)
                )

        # ====================================================
        # Coverage percentage
        # ====================================================

        route_coverage_percent = round(
            (
                len(matched_routes)
                / len(routes)
                * 100
            ),
            2
        )

        # ====================================================
        # Per workflow route hits
        # ====================================================

        per_workflow_route_hits = {}

        for workflow in sorted(
            workflow_operations
        ):

            observed = workflow_operations[
                workflow
            ]

            hits = []

            for route in routes:

                if microservices_mode:

                    found = (
                        route
                        in observed
                    )

                else:

                    found = (
                        route
                        in observed
                    )

                if found:

                    hits.append(
                        route_to_string(route)
                    )

            per_workflow_route_hits[
                workflow
            ] = hits

        # ====================================================
        # Store results
        # ====================================================

        results[sampling] = {

            "sampling": sampling,

            "sampling_label": (
                SAMPLING_LABELS[sampling]
            ),

            "architecture": (
                "microservices"
                if microservices_mode
                else "monolith"
            ),

            "static_route_count": len(
                routes
            ),

            "total_workflow_runs": len(
                trace_files
            ),

            "total_traces": total_traces,

            "total_spans": total_spans,

            "matched_route_count": len(
                matched_routes
            ),

            "missing_route_count": len(
                missing_routes
            ),

            "route_coverage_percent": (
                route_coverage_percent
            ),

            "matched_routes": (
                matched_routes
            ),

            "missing_routes": (
                missing_routes
            ),

            "per_workflow_route_hits": (
                per_workflow_route_hits
            )
        }

        # ====================================================
        # Print result
        # ====================================================

        print()

        print(
            f"  Workflow-runs : "
            f"{len(trace_files)}"
        )

        print(
            f"  Traces        : "
            f"{total_traces}"
        )

        print(
            f"  Spans         : "
            f"{total_spans}"
        )

        print(
            f"  Routes        : "
            f"{len(matched_routes)} / "
            f"{len(routes)}"
        )

        print(
            f"  Coverage      : "
            f"{route_coverage_percent}%"
        )

        if missing_routes:

            print(
                "  Missing routes:"
            )

            for route in missing_routes:

                print(
                    f"    - {route}"
                )

    # ========================================================
    # Save JSON
    # ========================================================

    json_output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        json_output,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2
        )

    print()
    print("=" * 70)

    print(
        f"JSON report saved to:\n"
        f"{json_output}"
    )

    # ========================================================
    # Excel output path
    # ========================================================

    if args.excel_out:

        excel_output = Path(
            args.excel_out
        )

    else:

        excel_output = (
            base_dir
            / "aggregate_coverage_by_sampling.xlsx"
        )

    excel_output.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # ========================================================
    # Create Excel
    # ========================================================

    create_excel_report(
        results,
        routes,
        excel_output
    )

    print(
        f"Excel report saved to:\n"
        f"{excel_output}"
    )

    print("=" * 70)
    print("Analysis completed successfully.")
    print("=" * 70)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()