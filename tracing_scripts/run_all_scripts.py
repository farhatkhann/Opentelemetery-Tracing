# """
# Runs every workflow's k6 script, back to back, for a single sampling level
# (and optionally across multiple run numbers for statistical averaging).

# Usage:
#     python run_all_scripts.py --sampling sample10
#     python run_all_scripts.py --sampling sample10 --runs 5
#     python run_all_scripts.py --sampling sample10 --runs 5 --resume
#     python run_all_scripts.py --sampling off --architecture monolith --service spring-petclinic

# Which services get scraped for metrics / queried for traces is resolved
# inside run_experiment.py (see WORKFLOW_CONFIG / SERVICE_CONFIG there) purely
# from --workflow-name, so this script doesn't need to know about services at
# all for the microservices architecture. --service is only used as a
# fallback for the monolith architecture (a single service, no lookup needed).

# This just calls run_experiment.py once per (workflow, run) combination, in
# order, waiting a bit between each so the server/Jaeger exporter has time to
# settle before the next workflow starts hammering it.
# """

# import argparse
# import subprocess
# import sys
# import time
# from pathlib import Path

# # ==========================================================
# # Workflow registry -- edit this list to match your actual
# # k6 script paths / names. The service(s) each workflow touches
# # live in run_experiment.py's WORKFLOW_CONFIG, not here.
# # ==========================================================

# WORKFLOWS = [
#     {"name": "browseOwners", "k6_script": "../k6/workflows/browseOwners.js"},
#     {"name": "ownerRegistration", "k6_script": "../k6/workflows/ownerRegistration.js"},
#     {"name": "ownerUpdate", "k6_script": "../k6/workflows/ownerUpdate.js"},
#     {"name": "petRegistration", "k6_script": "../k6/workflows/petRegistration.js"},
#     {"name": "visitRegistration", "k6_script": "../k6/workflows/visitRegistration.js"},
#     {"name": "mixedWorkflow", "k6_script": "../k6/workflows/mixedWorkflow.js"},
# ]

# # ==========================================================
# # CLI arguments
# # ==========================================================

# parser = argparse.ArgumentParser(
#     description="Run all workflows sequentially for one sampling level"
# )

# parser.add_argument("--sampling", required=True, help="Sampling configuration, e.g. sample10")
# parser.add_argument("--architecture", default="microservices", choices=["monolith", "microservices"])
# parser.add_argument(
#     "--service",
#     default="spring-petclinic",
#     help="Fallback service name (only used for the monolith architecture, "
#          "or if a workflow isn't found in run_experiment.py's WORKFLOW_CONFIG)"
# )
# parser.add_argument("--runs", type=int, default=1, help="Number of runs per workflow (default 1)")
# parser.add_argument("--pause", type=int, default=15,
#                      help="Seconds to wait between workflows, letting the server/exporter settle")
# parser.add_argument("--skip-reset", action="store_true")
# parser.add_argument(
#     "--resume",
#     action="store_true",
#     help="Skip (workflow, run) combinations that already have a summary.json "
#          "on disk, instead of re-running them. Useful for picking back up "
#          "after a crash partway through the full set."
# )
# parser.add_argument(
#     "--stop-on-failure",
#     action="store_true",
#     help="Abort the whole batch on the first run_experiment.py failure, "
#          "instead of logging it and continuing to the next workflow/run."
# )

# args = parser.parse_args()

# BASE_DIR = Path("../datasets/traces") / args.architecture / args.sampling


# def already_done(workflow_name, run):
#     """Check if this workflow/run already has a completed summary.json."""
#     summary_file = BASE_DIR / workflow_name / f"run{run}" / "summary.json"
#     return summary_file.exists()


# # ==========================================================
# # Main loop
# # ==========================================================

# total_jobs = len(WORKFLOWS) * args.runs
# completed = 0
# skipped = 0
# failed = []

# print("=" * 60)
# print(f"Running {len(WORKFLOWS)} workflows x {args.runs} run(s) "
#       f"= {total_jobs} total jobs")
# print(f"Sampling      : {args.sampling}")
# print(f"Architecture  : {args.architecture}")
# print(f"Resume mode   : {args.resume}")
# print("=" * 60)

# job_index = 0

# for workflow in WORKFLOWS:

#     for run in range(1, args.runs + 1):

#         job_index += 1

#         print(f"\n[{job_index}/{total_jobs}] {workflow['name']} - run {run}")

#         if args.resume and already_done(workflow["name"], run):
#             print(f"  -> Already completed (summary.json exists), skipping.")
#             skipped += 1
#             continue

#         command = [
#             sys.executable,
#             "run_experiment.py",
#             "--service", args.service,
#             "--architecture", args.architecture,
#             "--sampling", args.sampling,
#             "--run", str(run),
#             "--k6-script", workflow["k6_script"],
#             "--workflow-name", workflow["name"],
#         ]

#         if args.skip_reset:
#             command.append("--skip-reset")

#         result = subprocess.run(command)

#         if result.returncode != 0:
#             print(f"  -> FAILED: {workflow['name']} run {run} "
#                   f"(exit code {result.returncode})")
#             failed.append((workflow["name"], run))

#             if args.stop_on_failure:
#                 print("\n--stop-on-failure set, aborting remaining jobs.")
#                 break
#         else:
#             completed += 1

#         # Give the server / OTEL exporter a moment to settle before the
#         # next workflow starts, so traces don't bleed across boundaries.
#         if job_index < total_jobs:
#             print(f"  Pausing {args.pause}s before next job...")
#             time.sleep(args.pause)

#     else:
#         continue
#     break  # only reached if the inner loop broke due to --stop-on-failure

# # ==========================================================
# # Summary
# # ==========================================================

# print("\n" + "=" * 60)
# print("Batch Run Summary")
# print("=" * 60)
# print(f"Completed : {completed}")
# print(f"Skipped   : {skipped} (already done, --resume)")
# print(f"Failed    : {len(failed)}")

# if failed:
#     print("\nFailed jobs:")
#     for name, run in failed:
#         print(f"  - {name} run {run}")
#     sys.exit(1)

# print("\nAll jobs finished successfully.")

"""
Runs every workflow's k6 script, back to back, for a single sampling level
(and optionally across multiple run numbers for statistical averaging).

Usage:
    python run_all_scripts.py --sampling sample10
    python run_all_scripts.py --sampling sample10 --runs 5
    python run_all_scripts.py --sampling sample10 --runs 5 --resume
    python run_all_scripts.py --sampling off --architecture monolith --service spring-petclinic

Which services get scraped for metrics / queried for traces is resolved
inside run_experiment.py (see WORKFLOW_CONFIG / SERVICE_CONFIG there) purely
from --workflow-name, so this script doesn't need to know about services at
all for the microservices architecture. --service is only used as a
fallback for the monolith architecture (a single service, no lookup needed).

This just calls run_experiment.py once per (workflow, run) combination, in
order, waiting a bit between each so the server/Jaeger exporter has time to
settle before the next workflow starts hammering it.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests

# ==========================================================
# Workflow registry -- edit this list to match your actual
# k6 script paths / names. The service(s) each workflow touches
# live in run_experiment.py's WORKFLOW_CONFIG, not here.
# ==========================================================

WORKFLOWS = [
    {"name": "browseOwners", "k6_script": "../k6/workflows/browseOwners.js"},
    {"name": "ownerRegistration", "k6_script": "../k6/workflows/ownerRegistration.js"},
    {"name": "ownerUpdate", "k6_script": "../k6/workflows/ownerUpdate.js"},
    {"name": "petRegistration", "k6_script": "../k6/workflows/petRegistration.js"},
    {"name": "visitRegistration", "k6_script": "../k6/workflows/visitRegistration.js"},
    {"name": "mixedWorkflow", "k6_script": "../k6/workflows/mixedWorkflow.js"},
]

# ==========================================================
# CLI arguments
# ==========================================================

parser = argparse.ArgumentParser(
    description="Run all workflows sequentially for one sampling level"
)

parser.add_argument("--sampling", required=True, help="Sampling configuration, e.g. sample10")
parser.add_argument("--architecture", default="microservices", choices=["monolith", "microservices"])
parser.add_argument(
    "--service",
    default="spring-petclinic",
    help="Fallback service name (only used for the monolith architecture, "
         "or if a workflow isn't found in run_experiment.py's WORKFLOW_CONFIG)"
)
parser.add_argument("--runs", type=int, default=1, help="Number of runs per workflow (default 1)")
parser.add_argument("--pause", type=int, default=15,
                     help="Seconds to wait between workflows, letting the server/exporter settle")
parser.add_argument("--skip-reset", action="store_true")
parser.add_argument(
    "--resume",
    action="store_true",
    help="Skip (workflow, run) combinations that already have a summary.json "
         "on disk, instead of re-running them. Useful for picking back up "
         "after a crash partway through the full set."
)
parser.add_argument(
    "--stop-on-failure",
    action="store_true",
    help="Abort the whole batch on the first run_experiment.py failure, "
         "instead of logging it and continuing to the next workflow/run."
)
parser.add_argument(
    "--restart-jaeger",
    action="store_true",
    help="Restart the 'jaeger' container after each (workflow, run) job. "
         "Jaeger's all-in-one image keeps every span in memory with no "
         "eviction, so long batches eventually hit the container's memory "
         "limit and get OOM-killed mid-run. Restarting between jobs (each "
         "of which has already had its traces exported to traces.json by "
         "run_experiment.py before this runs) keeps memory bounded. Adds "
         "~5-15s per job while Jaeger comes back up."
)
parser.add_argument(
    "--jaeger-container", default="jaeger",
    help="Container/service name for Jaeger, used with --restart-jaeger "
         "(default: jaeger)"
)
parser.add_argument(
    "--jaeger-url", default="http://localhost:16686",
    help="Jaeger query API base URL, used with --restart-jaeger to confirm "
         "it's back up before the next job starts"
)
parser.add_argument(
    "--jaeger-ready-timeout", type=int, default=60,
    help="Max seconds to wait for Jaeger's query API to respond after a "
         "restart before giving up and continuing anyway"
)

args = parser.parse_args()

BASE_DIR = Path("../datasets/traces") / args.architecture / args.sampling


def already_done(workflow_name, run):
    """Check if this workflow/run already has a completed summary.json."""
    summary_file = BASE_DIR / workflow_name / f"run{run}" / "summary.json"
    return summary_file.exists()


def restart_jaeger_and_wait():
    """
    Restart the jaeger container to flush its in-memory span store, then
    poll its query API until it responds (or we time out). By the time
    this runs, run_experiment.py has already exported the just-finished
    job's traces to traces.json, so clearing jaeger's memory here is safe
    -- nothing from the completed job is lost.
    """
    print(f"  Restarting '{args.jaeger_container}' to clear trace memory...")

    result = subprocess.run(
        ["docker", "compose", "restart", args.jaeger_container],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  ⚠️  'docker compose restart {args.jaeger_container}' failed:")
        print(f"      {result.stderr.strip()}")
        print("  Continuing anyway -- next job's trace collection may fail.")
        return

    deadline = time.time() + args.jaeger_ready_timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{args.jaeger_url}/api/services", timeout=3)
            if resp.status_code == 200:
                print("  Jaeger is back up.")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)

    print(f"  ⚠️  Jaeger didn't respond within {args.jaeger_ready_timeout}s "
          "after restart -- continuing anyway, next job may see connection errors.")


# ==========================================================
# Main loop
# ==========================================================

total_jobs = len(WORKFLOWS) * args.runs
completed = 0
skipped = 0
failed = []

print("=" * 60)
print(f"Running {len(WORKFLOWS)} workflows x {args.runs} run(s) "
      f"= {total_jobs} total jobs")
print(f"Sampling      : {args.sampling}")
print(f"Architecture  : {args.architecture}")
print(f"Resume mode   : {args.resume}")
print("=" * 60)

job_index = 0

for workflow in WORKFLOWS:

    for run in range(1, args.runs + 1):

        job_index += 1

        print(f"\n[{job_index}/{total_jobs}] {workflow['name']} - run {run}")

        if args.resume and already_done(workflow["name"], run):
            print(f"  -> Already completed (summary.json exists), skipping.")
            skipped += 1
            continue

        command = [
            sys.executable,
            "run_experiment.py",
            "--service", args.service,
            "--architecture", args.architecture,
            "--sampling", args.sampling,
            "--run", str(run),
            "--k6-script", workflow["k6_script"],
            "--workflow-name", workflow["name"],
        ]

        if args.skip_reset:
            command.append("--skip-reset")

        result = subprocess.run(command)

        if result.returncode != 0:
            print(f"  -> FAILED: {workflow['name']} run {run} "
                  f"(exit code {result.returncode})")
            failed.append((workflow["name"], run))

            if args.stop_on_failure:
                print("\n--stop-on-failure set, aborting remaining jobs.")
                break
        else:
            completed += 1

        if args.restart_jaeger:
            restart_jaeger_and_wait()

        # Give the server / OTEL exporter a moment to settle before the
        # next workflow starts, so traces don't bleed across boundaries.
        if job_index < total_jobs:
            print(f"  Pausing {args.pause}s before next job...")
            time.sleep(args.pause)

    else:
        continue
    break  # only reached if the inner loop broke due to --stop-on-failure

# ==========================================================
# Summary
# ==========================================================

print("\n" + "=" * 60)
print("Batch Run Summary")
print("=" * 60)
print(f"Completed : {completed}")
print(f"Skipped   : {skipped} (already done, --resume)")
print(f"Failed    : {len(failed)}")

if failed:
    print("\nFailed jobs:")
    for name, run in failed:
        print(f"  - {name} run {run}")
    sys.exit(1)

print("\nAll jobs finished successfully.")