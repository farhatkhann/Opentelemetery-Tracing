# import argparse
# import json
# import subprocess
# import sys
# import time
# # from datetime import datetime
# from datetime import datetime, timezone
# from pathlib import Path
# import requests
# import re

# def read_k6_metrics(summary_file):

#     with open(summary_file, "r") as f:
#         summary = json.load(f)

#     metrics = summary["metrics"]

#     total_requests = metrics["http_reqs"]["count"]

#     failed_rate = metrics["http_req_failed"]["value"]

#     failed_requests = round(total_requests * failed_rate)

#     return {

#         "response_time_ms":
#             round(metrics["http_req_duration"]["avg"], 2),

#         "throughput_req_per_sec":
#             round(metrics["http_reqs"]["rate"], 2),

#         "total_requests":
#             total_requests,

#         "failed_requests":
#             failed_requests,

#         "failed_request_rate_percent":
#             round(failed_rate * 100, 2)
#     }

# def read_node_metrics(url="http://localhost:8080/actuator/prometheus"):
#     """
#     Read CPU usage and total JVM memory from Spring Boot Actuator Prometheus endpoint.
#     """

#     response = requests.get(url, timeout=5)
#     response.raise_for_status()

#     text = response.text

#     # Process CPU usage (0.0 - 1.0)
#     cpu_match = re.search(
#         r"^process_cpu_usage\s+([0-9.E+-]+)",
#         text,
#         re.MULTILINE
#     )

#     # Heap memory
#     heap_matches = re.findall(
#         r'^jvm_memory_used_bytes\{.*area="heap".*\}\s+([0-9.E+-]+)',
#         text,
#         re.MULTILINE
#     )

#     # Non-heap memory
#     nonheap_matches = re.findall(
#         r'^jvm_memory_used_bytes\{.*area="nonheap".*\}\s+([0-9.E+-]+)',
#         text,
#         re.MULTILINE
#     )

#     heap_bytes = sum(float(x) for x in heap_matches)
#     nonheap_bytes = sum(float(x) for x in nonheap_matches)

#     total_memory_mb = (heap_bytes + nonheap_bytes) / (1024 * 1024)

#     cpu_usage = float(cpu_match.group(1)) if cpu_match else 0

#     return {
#         "cpu_usage": cpu_usage,
#         "memory_mb": round(total_memory_mb, 2)
#     }

# def to_jaeger_us(dt: datetime, buffer_seconds: float = 0) -> int:
#     """Convert datetime to microseconds since epoch, Jaeger's expected format."""
#     return int((dt.timestamp() + buffer_seconds) * 1_000_000)

# # ----------------------------------------------------
# # Command-line arguments
# # ----------------------------------------------------

# parser = argparse.ArgumentParser(description="Run Observability Experiment")

# parser.add_argument(
#     "--service",
#     required=True,
#     help="Service name registered in Jaeger"
# )

# parser.add_argument(
#     "--architecture",
#     required=True,
#     choices=["monolith", "microservices"]
# )

# parser.add_argument(
#     "--sampling",
#     required=True,
#     help="Sampling configuration"
# )

# parser.add_argument(
#     "--run",
#     type=int,
#     default=1
# )

# parser.add_argument(
#     "--k6-script",
#     required=True,
#     help="Path to k6 script"
# )

# parser.add_argument(
#     "--wait",
#     type=int,
#     default=5,
#     help="Seconds to wait after k6 completes"
# )

# args = parser.parse_args()

# # ----------------------------------------------------
# # Create experiment folder
# # ----------------------------------------------------

# experiment_dir = (
#     Path("../datasets")
#     / "traces"
#     / args.architecture
#     / args.sampling
#     / f"run{args.run}"
# )

# experiment_dir.mkdir(parents=True, exist_ok=True)

# # ----------------------------------------------------
# # Record experiment start
# # ----------------------------------------------------

# print("=" * 60)
# print("Starting Experiment")
# print("=" * 60)

# start_time = datetime.now(timezone.utc)

# print(f"Start Time : {start_time.isoformat()} UTC")

# before_metrics = read_node_metrics()

# # ----------------------------------------------------
# # Run k6
# # ----------------------------------------------------

# print("\nRunning k6...")

# # k6_command = [
# #     "k6",
# #     "run",
# #     args.k6_script
# # ]

# k6_summary = experiment_dir / "k6_summary.json"

# k6_command = [
#     "k6",
#     "run",
#     "--summary-export",
#     str(k6_summary),
#     args.k6_script
# ]

# result = subprocess.run(k6_command)

# if result.returncode != 0:
#     print("\n❌ k6 execution failed.")
#     sys.exit(1)

# print("\nk6 completed successfully.")

# after_metrics = read_node_metrics()
# # ----------------------------------------------------
# # Read k6 Summary
# # ----------------------------------------------------

# k6_metrics = read_k6_metrics(k6_summary)
# node_metrics = read_node_metrics()

# print("\nPerformance Metrics")

# print(f"Average Response Time : {k6_metrics['response_time_ms']} ms")

# print(f"Throughput            : {k6_metrics['throughput_req_per_sec']} req/s")

# print(f"Failed Requests       : {k6_metrics['failed_requests']}")

# print(f"Total Requests        : {k6_metrics['total_requests']}")

# # ----------------------------------------------------
# # Wait for Jaeger exporter
# # ----------------------------------------------------

# print(f"\nWaiting {args.wait} seconds for traces...")

# time.sleep(args.wait)

# end_time = datetime.now(timezone.utc)
# start_us = to_jaeger_us(start_time, buffer_seconds=-2)   # 2s earlier, catch early spans
# end_us = to_jaeger_us(end_time, buffer_seconds=5)          # 5s later, catch flushed spans
# experiment_duration = (
#     end_time - start_time
# ).total_seconds()
# print(f"End Time : {end_time.isoformat()} UTC")

# # start_ts = int((start_time.timestamp() - 10) * 1_000_000)
# # end_ts = int((end_time.timestamp() + 15) * 1_000_000)

# # cpu_used = (
# #     after_metrics["cpu_seconds"]
# #     - before_metrics["cpu_seconds"]
# # )

# # cpu_utilization = (
# #     cpu_used / experiment_duration
# # ) * 100

# cpu_utilization = after_metrics["cpu_usage"] * 100

# memory_usage = after_metrics["memory_mb"]

# # ----------------------------------------------------
# # Save experiment info
# # ----------------------------------------------------

# # experiment = {

# #     "architecture": args.architecture,

# #     "service": args.service,

# #     "sampling": args.sampling,

# #     "run": args.run,

# #     "start_time": start_time.isoformat(),

# #     "end_time": end_time.isoformat(),

# #     "k6_script": args.k6_script
# # }

# experiment = {

#     "architecture": args.architecture,

#     "service": args.service,

#     "sampling": args.sampling,

#     "run": args.run,

#     "start_time": start_time.isoformat(),

#     "end_time": end_time.isoformat(),

#     "k6_script": args.k6_script,

#     "performance_metrics": {

#         "average_response_time_ms":
#             k6_metrics["response_time_ms"],

#         "throughput_req_per_sec":
#             k6_metrics["throughput_req_per_sec"],

#         "failed_requests":
#             k6_metrics["failed_requests"],

#         "total_requests":
#             k6_metrics["total_requests"]
#     },
#     "resource_metrics": {

#     "cpu_utilization_percent":
#         round(cpu_utilization, 2),

#     "memory_usage_mb":
#         round(after_metrics["memory_mb"], 2)
#     },
#     "trace_window": {
#     "start_us": start_us,
#     "end_us": end_us,
#     },
# }

# experiment_file = experiment_dir / "experiment.json"

# with open(experiment_file, "w") as f:
#     json.dump(experiment, f, indent=4)

# print("\nExperiment metadata saved.")

# # ----------------------------------------------------
# # Call collect_traces.py
# # ----------------------------------------------------

# print("\nCollecting traces from Jaeger...")

# collect_command = [
#     sys.executable,
#     "collect_traces.py",
#     "--service", args.service,
#     "--architecture", args.architecture,
#     "--sampling", args.sampling,
#     "--run", str(args.run),
#     "--start", str(start_us),
#     "--end", str(end_us)
# ]

# result = subprocess.run(collect_command)

# if result.returncode != 0:
#     print("Trace collection failed.")
#     sys.exit(1)

# print("\nExperiment Finished Successfully.")

import argparse
import json
import subprocess
import sys
import time
import os
from datetime import datetime, timezone
from pathlib import Path
import requests
import re


def read_k6_metrics(summary_file):

    with open(summary_file, "r") as f:
        summary = json.load(f)

    metrics = summary["metrics"]

    total_requests = metrics["http_reqs"]["count"]
    failed_rate = metrics["http_req_failed"]["value"]
    failed_requests = round(total_requests * failed_rate)

    return {
        "response_time_ms": round(metrics["http_req_duration"]["avg"], 2),
        "throughput_req_per_sec": round(metrics["http_reqs"]["rate"], 2),
        "total_requests": total_requests,
        "failed_requests": failed_requests,
        "failed_request_rate_percent": round(failed_rate * 100, 2)
    }


def read_node_metrics(url="http://localhost:8080/actuator/prometheus"):
    """
    Read cumulative CPU time and total JVM memory from Spring Boot
    Actuator's Prometheus endpoint.

    NOTE: process_cpu_time_seconds_total requires the custom
    ProcessCpuTimeMetricConfig bean (see ProcessCpuTimeMetricConfig.java).
    If this comes back as 0, confirm the bean is registered:
        curl http://localhost:8080/actuator/prometheus | grep process_cpu_time_seconds_total
    """

    response = requests.get(url, timeout=5)
    response.raise_for_status()

    text = response.text

    num = r"([0-9.eE+-]+)"

    # Cumulative CPU-seconds since process start (counter, not a ratio).
    # This is the JVM equivalent of Node's process_cpu_seconds_total.
    cpu_match = re.search(
        rf"^process_cpu_time_ns_total\s+{num}",
        text,
        re.MULTILINE
    )

    heap_matches = re.findall(
        rf'^jvm_memory_used_bytes\{{.*area="heap".*\}}\s+{num}',
        text,
        re.MULTILINE
    )

    nonheap_matches = re.findall(
        rf'^jvm_memory_used_bytes\{{.*area="nonheap".*\}}\s+{num}',
        text,
        re.MULTILINE
    )

    if cpu_match is None:
        print("⚠️  process_cpu_time_ns_total not found in /actuator/prometheus "
              "— is ProcessCpuTimeMetricConfig registered in your Spring Boot app?")

    if cpu_match:
        cpu_time_ns = float(cpu_match.group(1))
        cpu_seconds = cpu_time_ns / 1_000_000_000
    else:
        print("⚠️ process_cpu_time_ns_total not found in /actuator/prometheus")
        cpu_seconds = 0.0

    heap_bytes = sum(float(x) for x in heap_matches)
    nonheap_bytes = sum(float(x) for x in nonheap_matches)
    memory_mb = (heap_bytes + nonheap_bytes) / (1024 * 1024)

    return {
        "cpu_seconds": cpu_seconds,
        "memory_mb": round(memory_mb, 2)
    }


def to_jaeger_us(dt: datetime, buffer_seconds: float = 0) -> int:
    """Convert datetime to microseconds since epoch, Jaeger's expected format."""
    return int((dt.timestamp() + buffer_seconds) * 1_000_000)


# ----------------------------------------------------
# Command-line arguments
# ----------------------------------------------------

parser = argparse.ArgumentParser(description="Run Observability Experiment")

parser.add_argument("--service", required=True, help="Service name registered in Jaeger")
parser.add_argument("--architecture", required=True, choices=["monolith", "microservices"])
parser.add_argument("--sampling", required=True, help="Sampling configuration")
parser.add_argument("--run", type=int, default=1)
parser.add_argument("--k6-script", required=True, help="Path to k6 script")
parser.add_argument("--wait", type=int, default=5, help="Seconds to wait after k6 completes")

parser.add_argument(
    "--skip-reset",
    action="store_true",
    help="Skip the pre-run test data reset (not recommended for repeated runs)"
)
parser.add_argument(
    "--workflow-name",
    default=None,
    help="Optional explicit workflow name for the output folder. If omitted, "
         "it's derived automatically from the k6 script filename "
         "(e.g. wishlist_workflow.js -> wishlist_workflow)."
)

args = parser.parse_args()

# ----------------------------------------------------
# Create experiment folder
# ----------------------------------------------------

# experiment_dir = (
#     Path("../datasets") / "traces" / args.architecture / args.sampling / f"run{args.run}"
# )
# experiment_dir.mkdir(parents=True, exist_ok=True)

workflow_name = args.workflow_name or Path(args.k6_script).stem

experiment_dir = (
    Path("../datasets") / "traces" / args.architecture / args.sampling / workflow_name / f"run{args.run}"
)
experiment_dir.mkdir(parents=True, exist_ok=True)

print(f"\nWorkflow      : {workflow_name}")
print(f"Output folder : {experiment_dir}")

# ----------------------------------------------------
# Record experiment start
# ----------------------------------------------------

print("=" * 60)
print("Starting Experiment")
print("=" * 60)

start_time = datetime.now(timezone.utc)
print(f"Start Time : {start_time.isoformat()} UTC")

before_metrics = read_node_metrics()

# ----------------------------------------------------
# Run k6
# ----------------------------------------------------

print("\nRunning k6...")

k6_summary = experiment_dir / "k6_summary.json"

k6_command = [
    "k6", "run",
    "--summary-export", str(k6_summary),
    args.k6_script
]

result = subprocess.run(k6_command)

if result.returncode != 0:
    print("\n❌ k6 execution failed.")
    sys.exit(1)

print("\nk6 completed successfully.")

after_metrics = read_node_metrics()

# ----------------------------------------------------
# Read k6 Summary
# ----------------------------------------------------

k6_metrics = read_k6_metrics(k6_summary)

print("\nPerformance Metrics")
print(f"Average Response Time : {k6_metrics['response_time_ms']} ms")
print(f"Throughput            : {k6_metrics['throughput_req_per_sec']} req/s")
print(f"Failed Requests       : {k6_metrics['failed_requests']}")
print(f"Total Requests        : {k6_metrics['total_requests']}")

# ----------------------------------------------------
# Wait for Jaeger exporter, then compute trace window
# ----------------------------------------------------

print(f"\nWaiting {args.wait} seconds for traces...")
time.sleep(args.wait)

end_time = datetime.now(timezone.utc)

start_us = to_jaeger_us(start_time, buffer_seconds=-10)   # 2s earlier, catch early spans
end_us = to_jaeger_us(end_time, buffer_seconds=20)          # 5s later, catch flushed spans

experiment_duration = (end_time - start_time).total_seconds()
print(f"End Time : {end_time.isoformat()} UTC")

# ----------------------------------------------------
# CPU utilization — same method as the Node.js script:
# delta of a cumulative counter, normalized by duration x core count.
# ----------------------------------------------------

cpu_used = after_metrics["cpu_seconds"] - before_metrics["cpu_seconds"]
cpu_count = os.cpu_count()

cpu_utilization = (
    (cpu_used / (experiment_duration * cpu_count)) * 100
    if experiment_duration and cpu_count else 0
)

memory_usage = after_metrics["memory_mb"]

# ----------------------------------------------------
# Save experiment info
# ----------------------------------------------------

experiment = {
    "architecture": args.architecture,
    "service": args.service,
    "sampling": args.sampling,
    "run": args.run,
    "start_time": start_time.isoformat(),
    "end_time": end_time.isoformat(),
    "k6_script": args.k6_script,

    "performance_metrics": {
        "average_response_time_ms": k6_metrics["response_time_ms"],
        "throughput_req_per_sec": k6_metrics["throughput_req_per_sec"],
        "failed_requests": k6_metrics["failed_requests"],
        "total_requests": k6_metrics["total_requests"]
    },

    "resource_metrics": {
        "logical_cpu_count": cpu_count,
        "cpu_time_before_seconds": round(before_metrics["cpu_seconds"], 4),
        "cpu_time_after_seconds": round(after_metrics["cpu_seconds"], 4),
        "cpu_time_used_seconds": round(cpu_used, 4),
        "cpu_utilization_percent": round(cpu_utilization, 2),
        "memory_usage_mb": round(memory_usage, 2)
    },

    "trace_window": {
        "start_us": start_us,
        "end_us": end_us
    }
}

experiment_file = experiment_dir / "experiment.json"

with open(experiment_file, "w") as f:
    json.dump(experiment, f, indent=4)

print("\nExperiment metadata saved.")

# ----------------------------------------------------
# Call collect_traces.py with the time window
# ----------------------------------------------------

print("\nCollecting traces from Jaeger...")

collect_command = [
    sys.executable,
    "collect_traces.py",
    "--service", args.service,
    "--architecture", args.architecture,
    "--sampling", args.sampling,
    "--workflow", workflow_name,
    "--run", str(args.run),
    "--start", str(start_us),
    "--end", str(end_us)
]

result = subprocess.run(collect_command)

if result.returncode != 0:
    print("Trace collection failed.")
    sys.exit(1)

print("\nExperiment Finished Successfully.")