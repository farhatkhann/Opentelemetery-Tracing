# import json
# from pathlib import Path
# from statistics import mean, stdev
# from openpyxl import Workbook, load_workbook

# # ==========================================================
# # Configuration
# # ==========================================================

# APPLICATION = "Grocery App Monolithic"

# BASE_DIR = Path("../datasets/traces/monolith")

# SAMPLINGS = {
#     "sampleoff": "Off",
#     "sample100": "100%",
#     "sample10": "10%",
#     "sample1": "1%"
# }

# RUNS = 5

# OUTPUT_FILE = BASE_DIR / "grocery_app_monolithic_results.xlsx"

# # ==========================================================
# # Create/Open Workbook
# # ==========================================================

# if OUTPUT_FILE.exists():
#     wb = load_workbook(OUTPUT_FILE)
#     ws = wb.active
# else:
#     wb = Workbook()
#     ws = wb.active
#     ws.title = "Results"

#     ws.append([
#         "Application",
#         "Service",
#         "Workflow",
#         "Sampling",
#         "Avg Response Time (ms)",
#         "SD",

#         "Throughput (req/s)",
#         "SD",

#         "Trace Count",
#         "SD",

#         "Span Count",
#         "SD",

#         "Unique Operations",
#         "SD",

#         "Trace File Size (KB)",
#         "SD",

#         "Avg Span Duration (µs)",
#         "SD",

#         "CPU Utilization (%)",
#         "SD",

#         "Memory Usage (MB)",
#         "SD"
#     ])

# # ==========================================================
# # Helper Functions
# # ==========================================================

# def get_existing_row(service, workflow, sampling):

#     for row in range(2, ws.max_row + 1):

#         if (
#             ws.cell(row, 2).value == service and
#             ws.cell(row, 3).value == workflow and
#             ws.cell(row, 4).value == sampling
#         ):
#             return row

#     return None


# def safe_mean(values):
#     return round(mean(values), 2) if values else 0


# def safe_sd(values):
#     if len(values) <= 1:
#         return 0
#     return round(stdev(values), 2)


# # ==========================================================
# # Process Each Sampling
# # ==========================================================

# for sampling_folder, sampling_display in SAMPLINGS.items():

#     response_times = []
#     throughputs = []
#     trace_counts = []
#     span_counts = []
#     unique_operations = []
#     trace_sizes = []
#     avg_span_durations = []
#     cpu_utils = []
#     memory_utils = []

#     workflow = None

#     # ----------------------------------------

#     for run in range(1, RUNS + 1):

#         folder = BASE_DIR / sampling_folder / f"run{run}"

#         experiment_file = folder / "experiment.json"
#         summary_file = folder / "summary.json"

#         if not experiment_file.exists():
#             print(f"Missing: {experiment_file}")
#             continue

#         if not summary_file.exists():
#             print(f"Missing: {summary_file}")
#             continue

#         with open(experiment_file, "r") as f:
#             experiment = json.load(f)

#         with open(summary_file, "r") as f:
#             summary = json.load(f)

#         # Read service name
#         service = experiment["service"]

#         # Extract workflow once
#         if workflow is None:
#             workflow = Path(
#                 experiment["k6_script"]
#             ).stem

#         # ---------------- Performance ----------------

#         response_times.append(
#             experiment["performance_metrics"]["average_response_time_ms"]
#         )

#         throughputs.append(
#             experiment["performance_metrics"]["throughput_req_per_sec"]
#         )

#         cpu_utils.append(
#             experiment["resource_metrics"]["cpu_utilization_percent"]
#         )

#         memory_utils.append(
#             experiment["resource_metrics"]["memory_usage_mb"]
#         )

#         # ---------------- Trace Metrics ----------------

#         trace_counts.append(
#             summary["trace_count"]
#         )

#         span_counts.append(
#             summary["span_count"]
#         )

#         unique_operations.append(
#             summary["unique_operations"]
#         )

#         trace_sizes.append(
#             summary["trace_file_size_kb"]
#         )

#         avg_span_durations.append(
#             summary["average_span_duration_us"]
#         )

#     if workflow is None:
#         continue

#     # =====================================================
#     # Final Row
#     # =====================================================

#     row = [

#         APPLICATION,

#         service,

#         workflow,

#         sampling_display,

#         safe_mean(response_times),
#         safe_sd(response_times),

#         safe_mean(throughputs),
#         safe_sd(throughputs),

#         safe_mean(trace_counts),
#         safe_sd(trace_counts),

#         safe_mean(span_counts),
#         safe_sd(span_counts),

#         safe_mean(unique_operations),
#         safe_sd(unique_operations),

#         safe_mean(trace_sizes),
#         safe_sd(trace_sizes),

#         safe_mean(avg_span_durations),
#         safe_sd(avg_span_durations),

#         safe_mean(cpu_utils),
#         safe_sd(cpu_utils),

#         safe_mean(memory_utils),
#         safe_sd(memory_utils)

#     ]

#     # =====================================================
#     # Update Existing Row
#     # =====================================================

#     existing_row = get_existing_row(
#     service,
#     workflow,
#     sampling_display
# )

#     if existing_row:

#         for col, value in enumerate(row, start=1):
#             ws.cell(existing_row, col).value = value

#         print(f"Updated: {workflow} - {sampling_display}")

#     else:

#         ws.append(row)

#         print(f"Added: {workflow} - {sampling_display}")

# # ==========================================================
# # Auto Adjust Column Width
# # ==========================================================

# for column_cells in ws.columns:

#     length = max(
#         len(str(cell.value)) if cell.value is not None else 0
#         for cell in column_cells
#     )

#     ws.column_dimensions[
#         column_cells[0].column_letter
#     ].width = length + 3

# # ==========================================================
# # Save Workbook
# # ==========================================================

# try:
#     wb.save(OUTPUT_FILE)

#     print("\n" + "=" * 60)
#     print("Results generated successfully")
#     print(f"Output File : {OUTPUT_FILE}")
#     print("=" * 60)

# except PermissionError:
#     print("\nERROR: Cannot save the Excel file.")
#     print("Please close 'grocery_app_monolithic_results.xlsx' if it is open in Excel and run the script again.")

import json
from pathlib import Path
from statistics import mean, stdev
from openpyxl import Workbook, load_workbook

# ==========================================================
# Configuration
# ==========================================================

APPLICATION = "Grocery App Monolithic"

BASE_DIR = Path("../datasets/traces/monolith")

# NOTE: these keys must match your actual folder names exactly, since
# they're used directly as BASE_DIR / sampling_folder. Double check
# against what run_experiment.py / collect_traces.py actually create --
# e.g. if your sampling arg was "off" (not "sampleoff"), the folder will
# be named "off", and this dict's key must match or that sampling level
# will silently produce zero rows (folder just won't be found below).
SAMPLINGS = {
    "off": "Off",
    "sample100": "100%",
    "sample10": "10%",
    "sample1": "1%"
}

RUNS = 5

OUTPUT_FILE = BASE_DIR / "grocery_app_monolithic_results.xlsx"

# ==========================================================
# Create/Open Workbook
# ==========================================================

if OUTPUT_FILE.exists():
    wb = load_workbook(OUTPUT_FILE)
    ws = wb.active
else:
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    ws.append([
        "Application",
        "Service",
        "Workflow",
        "Sampling",
        "Avg Response Time (ms)",
        "SD",

        "Throughput (req/s)",
        "SD",

        "Trace Count",
        "SD",

        "Span Count",
        "SD",

        "Unique Operations",
        "SD",

        "Trace File Size (KB)",
        "SD",

        "Avg Span Duration (µs)",
        "SD",

        "CPU Utilization (%)",
        "SD",

        "Memory Usage (MB)",
        "SD"
    ])

# ==========================================================
# Helper Functions
# ==========================================================

def get_existing_row(service, workflow, sampling):

    for row in range(2, ws.max_row + 1):

        if (
            ws.cell(row, 2).value == service and
            ws.cell(row, 3).value == workflow and
            ws.cell(row, 4).value == sampling
        ):
            return row

    return None


def safe_mean(values):
    return round(mean(values), 2) if values else 0


def safe_sd(values):
    if len(values) <= 1:
        return 0
    return round(stdev(values), 2)


def discover_workflow_folders(sampling_dir):
    """
    Returns a list of workflow subfolder names found directly under
    the given sampling directory (new structure:
    sampling/{workflow}/run{N}/...). Skips anything that isn't a
    directory, and skips a directory that looks like an old-style
    "runN" folder left over from before the workflow-subfolder fix
    (those belong to the old flat layout and aren't handled here --
    see the migration note at the bottom of this script).
    """
    if not sampling_dir.exists():
        return []

    workflow_folders = []

    for entry in sorted(sampling_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("run"):
            # Old flat-structure leftover (sampling/runN directly, no
            # workflow subfolder) -- not handled by this script anymore.
            print(f"  Skipping old-structure folder (no workflow subfolder): {entry}")
            continue
        workflow_folders.append(entry.name)

    return workflow_folders


# ==========================================================
# Process Each Sampling x Workflow
# ==========================================================

for sampling_folder, sampling_display in SAMPLINGS.items():

    sampling_dir = BASE_DIR / sampling_folder

    workflow_folders = discover_workflow_folders(sampling_dir)

    if not workflow_folders:
        print(f"No workflow folders found under: {sampling_dir}")
        continue

    for workflow_folder in workflow_folders:

        response_times = []
        throughputs = []
        trace_counts = []
        span_counts = []
        unique_operations = []
        trace_sizes = []
        avg_span_durations = []
        cpu_utils = []
        memory_utils = []

        service = None
        workflow = None

        # ----------------------------------------

        for run in range(1, RUNS + 1):

            folder = sampling_dir / workflow_folder / f"run{run}"

            experiment_file = folder / "experiment.json"
            summary_file = folder / "summary.json"

            if not experiment_file.exists():
                print(f"Missing: {experiment_file}")
                continue

            if not summary_file.exists():
                print(f"Missing: {summary_file}")
                continue

            with open(experiment_file, "r") as f:
                experiment = json.load(f)

            with open(summary_file, "r") as f:
                summary = json.load(f)

            # Read service name
            service = experiment["service"]

            # Prefer the explicit "workflow" field (written by the fixed
            # run_experiment.py); fall back to deriving it from the k6
            # script path for older experiment.json files that predate
            # that field.
            if workflow is None:
                workflow = experiment.get("workflow") or Path(
                    experiment["k6_script"]
                ).stem

            # ---------------- Performance ----------------

            response_times.append(
                experiment["performance_metrics"]["average_response_time_ms"]
            )

            throughputs.append(
                experiment["performance_metrics"]["throughput_req_per_sec"]
            )

            cpu_utils.append(
                experiment["resource_metrics"]["cpu_utilization_percent"]
            )

            memory_utils.append(
                experiment["resource_metrics"]["memory_usage_mb"]
            )

            # ---------------- Trace Metrics ----------------

            trace_counts.append(
                summary["trace_count"]
            )

            span_counts.append(
                summary["span_count"]
            )

            unique_operations.append(
                summary["unique_operations"]
            )

            trace_sizes.append(
                summary["trace_file_size_kb"]
            )

            avg_span_durations.append(
                summary["average_span_duration_us"]
            )

        if workflow is None:
            # No valid run folders found for this workflow at all.
            continue

        # =====================================================
        # Final Row
        # =====================================================

        row = [

            APPLICATION,

            service,

            workflow,

            sampling_display,

            safe_mean(response_times),
            safe_sd(response_times),

            safe_mean(throughputs),
            safe_sd(throughputs),

            safe_mean(trace_counts),
            safe_sd(trace_counts),

            safe_mean(span_counts),
            safe_sd(span_counts),

            safe_mean(unique_operations),
            safe_sd(unique_operations),

            safe_mean(trace_sizes),
            safe_sd(trace_sizes),

            safe_mean(avg_span_durations),
            safe_sd(avg_span_durations),

            safe_mean(cpu_utils),
            safe_sd(cpu_utils),

            safe_mean(memory_utils),
            safe_sd(memory_utils)

        ]

        # =====================================================
        # Update Existing Row
        # =====================================================

        existing_row = get_existing_row(
            service,
            workflow,
            sampling_display
        )

        if existing_row:

            for col, value in enumerate(row, start=1):
                ws.cell(existing_row, col).value = value

            print(f"Updated: {workflow} - {sampling_display}")

        else:

            ws.append(row)

            print(f"Added: {workflow} - {sampling_display}")

# ==========================================================
# Auto Adjust Column Width
# ==========================================================

for column_cells in ws.columns:

    length = max(
        len(str(cell.value)) if cell.value is not None else 0
        for cell in column_cells
    )

    ws.column_dimensions[
        column_cells[0].column_letter
    ].width = length + 3

# ==========================================================
# Save Workbook
# ==========================================================

try:
    wb.save(OUTPUT_FILE)

    print("\n" + "=" * 60)
    print("Results generated successfully")
    print(f"Output File : {OUTPUT_FILE}")
    print("=" * 60)

except PermissionError:
    print("\nERROR: Cannot save the Excel file.")
    print("Please close 'grocery_app_monolithic_results.xlsx' if it is open in Excel and run the script again.")