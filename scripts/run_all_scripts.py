"""
Runs every workflow's k6 script, back to back, for a single sampling level
(and optionally across multiple run numbers for statistical averaging).

Usage:
    python run_all_workflows.py --sampling sample10
    python run_all_workflows.py --sampling sample10 --runs 5
    python run_all_workflows.py --sampling sample10 --runs 5 --resume
    python run_all_workflows.py --sampling off --architecture microservices --service my-service

This just calls run_experiment.py once per (workflow, run) combination, in
order, waiting a bit between each so the server/Jaeger exporter has time to
settle before the next workflow starts hammering it.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# ==========================================================
# Workflow registry -- edit this list to match your actual
# k6 script paths / names.
# ==========================================================

WORKFLOWS = [
    {"name": "login", "k6_script": "../k6/workflows/login.js"},
    {"name": "signup", "k6_script": "../k6/workflows/signup.js"},
    {"name": "browse_product", "k6_script": "../k6/workflows/browse_product.js"},
    {"name": "wishlist_workflow", "k6_script": "../k6/workflows/wishlist_workflow.js"},
    {"name": "cart_workflow", "k6_script": "../k6/workflows/cart_workflow.js"},
    {"name": "checkout_workflow", "k6_script": "../k6/workflows/checkout_workflow.js"},
    {"name": "customer_workflow", "k6_script": "../k6/workflows/customer_workflow.js"},
]

# ==========================================================
# CLI arguments
# ==========================================================

parser = argparse.ArgumentParser(
    description="Run all workflows sequentially for one sampling level"
)

parser.add_argument("--sampling", required=True, help="Sampling configuration, e.g. sample10")
parser.add_argument("--architecture", default="microservices", choices=["monolith", "microservices"])
parser.add_argument("--service", default="grocery-monolith", help="Service name registered in Jaeger")
parser.add_argument("--runs", type=int, default=1, help="Number of runs per workflow (default 1)")
parser.add_argument("--test-user-email", default="test@example.com")
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

args = parser.parse_args()

BASE_DIR = Path("../datasets/traces") / args.architecture / args.sampling


def already_done(workflow_name, run):
    """Check if this workflow/run already has a completed summary.json."""
    summary_file = BASE_DIR / workflow_name / f"run{run}" / "summary.json"
    return summary_file.exists()


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
            # "--test-user-email", args.test_user_email,
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