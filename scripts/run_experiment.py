# import argparse
# import json
# import subprocess
# import sys
# import time
# import os
# from datetime import datetime, timezone
# from pathlib import Path

# import requests
# import re

# # ============================================================
# # Per-service configuration
# #
# # Add an entry here for every microservice you want metrics from.
# # "prometheus_url"  -> the service's Prometheus/Micrometer scrape endpoint
# # "jaeger_service"  -> the exact service name it registers under in Jaeger
# # ============================================================

# SERVICE_CONFIG = {
#     "customer": {
#         "prometheus_url": "http://localhost:8001/metrics",
#         "jaeger_service": "customer-service",
#     },
#     "products": {
#         "prometheus_url": "http://localhost:8002/metrics",
#         "jaeger_service": "product-service",
#     },
#     "shopping": {
#         "prometheus_url": "http://localhost:8003/metrics",
#         "jaeger_service": "shopping-service",
#     },
#     # Add more services here as they come online, e.g.:
#     # "order": {
#     #     "prometheus_url": "http://localhost:8004/metrics",
#     #     "jaeger_service": "order-service",
#     # },
# }

# # ============================================================
# # Per-workflow configuration
# #
# # Maps a workflow name (derived from the k6 script filename, or passed
# # explicitly via --workflow-name) to the list of services that
# # participate in it. Keys in "services" must exist in SERVICE_CONFIG.
# # ============================================================

# WORKFLOW_CONFIG = {
#     "login": {
#         "services": ["customer"],
#     },
#     "signup": {
#             "services": ["customer"],
#     },
#     "customer_workflow": {
#         "services": ["customer"],
#     },
#     "browse_product": {
#         "services": ["products"],
#     },
#     "wishlist_workflow": {
#         "services": ["products"],
#     },
#     "cart_workflow": {
#             "services": ["customer", "products", "shopping"],
#     },
#     "checkout_workflow": {
#         "services": ["customer", "products", "shopping"],
#     },
#     # Add more workflows here, matching your k6 script names, e.g.:
#     # "wishlist_workflow": {
#     #     "services": ["customer", "products"],
#     # },
# }


# def read_k6_metrics(summary_file):

#     with open(summary_file, "r") as f:
#         summary = json.load(f)

#     metrics = summary["metrics"]

#     total_requests = metrics["http_reqs"]["count"]
#     failed_rate = metrics["http_req_failed"]["value"]
#     failed_requests = round(total_requests * failed_rate)

#     return {
#         "response_time_ms": round(metrics["http_req_duration"]["avg"], 2),
#         "throughput_req_per_sec": round(metrics["http_reqs"]["rate"], 2),
#         "total_requests": total_requests,
#         "failed_requests": failed_requests,
#         "failed_request_rate_percent": round(failed_rate * 100, 2)
#     }


# def read_node_metrics(url):
#     """
#     Read cumulative CPU time and resident memory from a service's
#     Prometheus endpoint. These services expose Node.js prom-client
#     default metrics, e.g.:

#         process_cpu_seconds_total       (counter, already in seconds)
#         process_resident_memory_bytes   (gauge, RSS)

#     (Despite the name, this works for any service exposing these two
#     standard prom-client/Prometheus process metrics.)
#     """

#     response = requests.get(url, timeout=5)
#     response.raise_for_status()

#     text = response.text

#     num = r"([0-9.eE+-]+)"

#     # Cumulative CPU-seconds since process start (counter, not a ratio).
#     cpu_match = re.search(
#         rf"^process_cpu_seconds_total\s+{num}",
#         text,
#         re.MULTILINE
#     )

#     memory_match = re.search(
#         rf"^process_resident_memory_bytes\s+{num}",
#         text,
#         re.MULTILINE
#     )

#     if cpu_match is None:
#         print(f"⚠️  process_cpu_seconds_total not found at {url} "
#               "— confirm this service exposes default prom-client process metrics.")
#         cpu_seconds = 0.0
#     else:
#         cpu_seconds = float(cpu_match.group(1))

#     if memory_match is None:
#         print(f"⚠️  process_resident_memory_bytes not found at {url}")
#         memory_mb = 0.0
#     else:
#         memory_bytes = float(memory_match.group(1))
#         memory_mb = memory_bytes / (1024 * 1024)

#     return {
#         "cpu_seconds": cpu_seconds,
#         "memory_mb": round(memory_mb, 2)
#     }


# def collect_all_service_metrics(services):
#     """Read Prometheus metrics for every service in the workflow."""
#     metrics = {}
#     for service in services:
#         url = SERVICE_CONFIG[service]["prometheus_url"]
#         try:
#             metrics[service] = read_node_metrics(url)
#         except requests.exceptions.RequestException as e:
#             print(f"⚠️  Failed to read metrics for '{service}' at {url}: {e}")
#             metrics[service] = {"cpu_seconds": 0.0, "memory_mb": 0.0}
#     return metrics


# def to_jaeger_us(dt: datetime, buffer_seconds: float = 0) -> int:
#     """Convert datetime to microseconds since epoch, Jaeger's expected format."""
#     return int((dt.timestamp() + buffer_seconds) * 1_000_000)


# # ----------------------------------------------------
# # Command-line arguments
# # ----------------------------------------------------

# parser = argparse.ArgumentParser(description="Run Observability Experiment")

# parser.add_argument(
#     "--workflow-name",
#     default=None,
#     help="Workflow name, must match a key in WORKFLOW_CONFIG. If omitted, "
#          "it's derived automatically from the k6 script filename "
#          "(e.g. checkout_workflow.js -> checkout_workflow)."
# )
# parser.add_argument(
#     "--service",
#     default=None,
#     help="Fallback: single service name (key in SERVICE_CONFIG) to use if "
#          "the workflow isn't found in WORKFLOW_CONFIG."
# )
# parser.add_argument("--architecture", required=True, choices=["monolith", "microservices"])
# parser.add_argument("--sampling", required=True, help="Sampling configuration")
# parser.add_argument("--run", type=int, default=1)
# parser.add_argument("--k6-script", required=True, help="Path to k6 script")
# parser.add_argument("--wait", type=int, default=5, help="Seconds to wait after k6 completes")
# parser.add_argument(
#     "--skip-reset",
#     action="store_true",
#     help="Skip the pre-run test data reset (not recommended for repeated runs)"
# )

# args = parser.parse_args()

# # ----------------------------------------------------
# # Resolve workflow -> services
# # ----------------------------------------------------

# workflow_name = args.workflow_name or Path(args.k6_script).stem

# if workflow_name in WORKFLOW_CONFIG:
#     services = WORKFLOW_CONFIG[workflow_name]["services"]
# elif args.service:
#     if args.service not in SERVICE_CONFIG:
#         print(f"❌ Unknown service '{args.service}'. Add it to SERVICE_CONFIG first.")
#         sys.exit(1)
#     services = [args.service]
# else:
#     print(
#         f"❌ Workflow '{workflow_name}' not found in WORKFLOW_CONFIG, and no "
#         f"--service fallback was given. Either add '{workflow_name}' to "
#         f"WORKFLOW_CONFIG with its list of services, or pass --service."
#     )
#     sys.exit(1)

# unknown = [s for s in services if s not in SERVICE_CONFIG]
# if unknown:
#     print(f"❌ Workflow '{workflow_name}' references unknown service(s) {unknown}. "
#           "Add them to SERVICE_CONFIG first.")
#     sys.exit(1)

# # ----------------------------------------------------
# # Create experiment folder
# # ----------------------------------------------------

# experiment_dir = (
#     Path("../datasets") / "traces" / args.architecture / args.sampling / workflow_name / f"run{args.run}"
# )
# experiment_dir.mkdir(parents=True, exist_ok=True)

# print(f"\nWorkflow      : {workflow_name}")
# print(f"Services      : {', '.join(services)}")
# print(f"Output folder : {experiment_dir}")

# # ----------------------------------------------------
# # Record experiment start
# # ----------------------------------------------------

# print("=" * 60)
# print("Starting Experiment")
# print("=" * 60)

# start_time = datetime.now(timezone.utc)
# print(f"Start Time : {start_time.isoformat()} UTC")

# before_metrics = collect_all_service_metrics(services)

# # ----------------------------------------------------
# # Run k6
# # ----------------------------------------------------

# print("\nRunning k6...")

# k6_summary = experiment_dir / "k6_summary.json"

# k6_command = [
#     "k6", "run",
#     "--summary-export", str(k6_summary),
#     args.k6_script
# ]

# result = subprocess.run(k6_command)

# if result.returncode != 0:
#     print("\n❌ k6 execution failed.")
#     sys.exit(1)

# print("\nk6 completed successfully.")

# after_metrics = collect_all_service_metrics(services)

# # ----------------------------------------------------
# # Read k6 Summary
# # ----------------------------------------------------

# k6_metrics = read_k6_metrics(k6_summary)

# print("\nPerformance Metrics")
# print(f"Average Response Time : {k6_metrics['response_time_ms']} ms")
# print(f"Throughput            : {k6_metrics['throughput_req_per_sec']} req/s")
# print(f"Failed Requests       : {k6_metrics['failed_requests']}")
# print(f"Total Requests        : {k6_metrics['total_requests']}")

# # ----------------------------------------------------
# # Wait for Jaeger exporter, then compute trace window
# # ----------------------------------------------------

# print(f"\nWaiting {args.wait} seconds for traces...")
# time.sleep(args.wait)

# end_time = datetime.now(timezone.utc)

# start_us = to_jaeger_us(start_time, buffer_seconds=-10)  # catch early spans
# end_us = to_jaeger_us(end_time, buffer_seconds=20)        # catch flushed spans

# experiment_duration = (end_time - start_time).total_seconds()
# print(f"End Time : {end_time.isoformat()} UTC")

# # ----------------------------------------------------
# # Per-service CPU utilization — delta of a cumulative counter,
# # normalized by duration x core count.
# # ----------------------------------------------------

# cpu_count = os.cpu_count()

# per_service_resource_metrics = {}
# for service in services:
#     cpu_used = after_metrics[service]["cpu_seconds"] - before_metrics[service]["cpu_seconds"]
#     cpu_utilization = (
#         (cpu_used / (experiment_duration * cpu_count)) * 100
#         if experiment_duration and cpu_count else 0
#     )
#     per_service_resource_metrics[service] = {
#         "cpu_time_before_seconds": round(before_metrics[service]["cpu_seconds"], 4),
#         "cpu_time_after_seconds": round(after_metrics[service]["cpu_seconds"], 4),
#         "cpu_time_used_seconds": round(cpu_used, 4),
#         "cpu_utilization_percent": round(cpu_utilization, 2),
#         "memory_usage_mb": round(after_metrics[service]["memory_mb"], 2),
#     }

# # ----------------------------------------------------
# # Save experiment info
# # ----------------------------------------------------

# experiment = {
#     "workflow": workflow_name,
#     "architecture": args.architecture,
#     "sampling": args.sampling,
#     "run": args.run,
#     "start_time": start_time.isoformat(),
#     "end_time": end_time.isoformat(),
#     "k6_script": args.k6_script,

#     "performance_metrics": {
#         "average_response_time_ms": k6_metrics["response_time_ms"],
#         "throughput_req_per_sec": k6_metrics["throughput_req_per_sec"],
#         "failed_requests": k6_metrics["failed_requests"],
#         "total_requests": k6_metrics["total_requests"]
#     },

#     "logical_cpu_count": cpu_count,

#     "services": per_service_resource_metrics,

#     "trace_window": {
#         "start_us": start_us,
#         "end_us": end_us
#     }
# }

# experiment_file = experiment_dir / "experiment.json"

# with open(experiment_file, "w") as f:
#     json.dump(experiment, f, indent=4)

# print("\nExperiment metadata saved.")

# # ----------------------------------------------------
# # Call collect_traces.py with the time window and every
# # jaeger service name involved in this workflow
# # ----------------------------------------------------

# print("\nCollecting traces from Jaeger...")

# jaeger_services = ",".join(SERVICE_CONFIG[s]["jaeger_service"] for s in services)

# collect_command = [
#     sys.executable,
#     "collect_traces.py",
#     "--services", jaeger_services,
#     "--architecture", args.architecture,
#     "--sampling", args.sampling,
#     "--workflow", workflow_name,
#     "--run", str(args.run),
#     "--start", str(start_us),
#     "--end", str(end_us)
# ]

# result = subprocess.run(collect_command)

# if result.returncode != 0:
#     print("Trace collection failed.")
#     sys.exit(1)

# print("\nExperiment Finished Successfully.")

# import argparse
# import json
# import subprocess
# import sys
# import time
# import os
# from datetime import datetime, timezone
# from pathlib import Path

# import requests
# import re

# # ============================================================
# # Per-service configuration
# #
# # Add an entry here for every microservice you want metrics from.
# # "prometheus_url"  -> the service's Prometheus/Micrometer scrape endpoint
# # "jaeger_service"  -> the exact service name it registers under in Jaeger
# # ============================================================

# SERVICE_CONFIG = {
#     "customer": {
#         "prometheus_url": "http://localhost:8001/metrics",
#         "jaeger_service": "customer-service",
#     },
#     "products": {
#         "prometheus_url": "http://localhost:8002/metrics",
#         "jaeger_service": "product-service",
#     },
#     "shopping": {
#         "prometheus_url": "http://localhost:8003/metrics",
#         "jaeger_service": "shopping-service",
#     },
#     # Add more services here as they come online, e.g.:
#     # "order": {
#     #     "prometheus_url": "http://localhost:8004/metrics",
#     #     "jaeger_service": "order-service",
#     # },
# }

# # ============================================================
# # Per-workflow configuration
# #
# # Maps a workflow name (derived from the k6 script filename, or passed
# # explicitly via --workflow-name) to the list of services that
# # participate in it. Keys in "services" must exist in SERVICE_CONFIG.
# # ============================================================

# WORKFLOW_CONFIG = {
#     "login": {
#         "services": ["customer"],
#     },
#     "browse_products": {
#         "services": ["products"],
#     },
#     "checkout": {
#         "services": ["customer", "products", "shopping"],
#     },
#     # Add more workflows here, matching your k6 script names, e.g.:
#     # "wishlist_workflow": {
#     #     "services": ["customer", "products"],
#     # },
# }


# def read_k6_metrics(summary_file):

#     with open(summary_file, "r") as f:
#         summary = json.load(f)

#     metrics = summary["metrics"]

#     total_requests = metrics["http_reqs"]["count"]
#     failed_rate = metrics["http_req_failed"]["value"]
#     failed_requests = round(total_requests * failed_rate)

#     return {
#         "response_time_ms": round(metrics["http_req_duration"]["avg"], 2),
#         "throughput_req_per_sec": round(metrics["http_reqs"]["rate"], 2),
#         "total_requests": total_requests,
#         "failed_requests": failed_requests,
#         "failed_request_rate_percent": round(failed_rate * 100, 2)
#     }


# def read_node_metrics(url):
#     """
#     Read cumulative CPU time and total JVM memory from a service's
#     Prometheus/Micrometer metrics endpoint.

#     NOTE: process_cpu_time_ns_total requires the custom
#     ProcessCpuTimeMetricConfig bean (see ProcessCpuTimeMetricConfig.java).
#     If this comes back as 0, confirm the bean is registered on that
#     service, e.g.:
#         curl http://localhost:8001/metrics | grep process_cpu_time_ns_total
#     """

#     response = requests.get(url, timeout=5)
#     response.raise_for_status()

#     text = response.text

#     num = r"([0-9.eE+-]+)"

#     # Cumulative CPU-seconds since process start (counter, not a ratio).
#     cpu_match = re.search(
#         rf"^process_cpu_time_ns_total\s+{num}",
#         text,
#         re.MULTILINE
#     )

#     heap_matches = re.findall(
#         rf'^jvm_memory_used_bytes\{{.*area="heap".*\}}\s+{num}',
#         text,
#         re.MULTILINE
#     )

#     nonheap_matches = re.findall(
#         rf'^jvm_memory_used_bytes\{{.*area="nonheap".*\}}\s+{num}',
#         text,
#         re.MULTILINE
#     )

#     if cpu_match is None:
#         print(f"⚠️  process_cpu_time_ns_total not found at {url} "
#               "— is ProcessCpuTimeMetricConfig registered on this service?")
#         cpu_seconds = 0.0
#     else:
#         cpu_time_ns = float(cpu_match.group(1))
#         cpu_seconds = cpu_time_ns / 1_000_000_000

#     heap_bytes = sum(float(x) for x in heap_matches)
#     nonheap_bytes = sum(float(x) for x in nonheap_matches)
#     memory_mb = (heap_bytes + nonheap_bytes) / (1024 * 1024)

#     return {
#         "cpu_seconds": cpu_seconds,
#         "memory_mb": round(memory_mb, 2)
#     }


# def collect_all_service_metrics(services):
#     """Read Prometheus metrics for every service in the workflow."""
#     metrics = {}
#     for service in services:
#         url = SERVICE_CONFIG[service]["prometheus_url"]
#         try:
#             metrics[service] = read_node_metrics(url)
#         except requests.exceptions.RequestException as e:
#             print(f"⚠️  Failed to read metrics for '{service}' at {url}: {e}")
#             metrics[service] = {"cpu_seconds": 0.0, "memory_mb": 0.0}
#     return metrics


# def to_jaeger_us(dt: datetime, buffer_seconds: float = 0) -> int:
#     """Convert datetime to microseconds since epoch, Jaeger's expected format."""
#     return int((dt.timestamp() + buffer_seconds) * 1_000_000)


# # ----------------------------------------------------
# # Command-line arguments
# # ----------------------------------------------------

# parser = argparse.ArgumentParser(description="Run Observability Experiment")

# parser.add_argument(
#     "--workflow-name",
#     default=None,
#     help="Workflow name, must match a key in WORKFLOW_CONFIG. If omitted, "
#          "it's derived automatically from the k6 script filename "
#          "(e.g. checkout_workflow.js -> checkout_workflow)."
# )
# parser.add_argument(
#     "--service",
#     default=None,
#     help="Fallback: single service name (key in SERVICE_CONFIG) to use if "
#          "the workflow isn't found in WORKFLOW_CONFIG."
# )
# parser.add_argument("--architecture", required=True, choices=["monolith", "microservices"])
# parser.add_argument("--sampling", required=True, help="Sampling configuration")
# parser.add_argument("--run", type=int, default=1)
# parser.add_argument("--k6-script", required=True, help="Path to k6 script")
# parser.add_argument("--wait", type=int, default=5, help="Seconds to wait after k6 completes")
# parser.add_argument(
#     "--skip-reset",
#     action="store_true",
#     help="Skip the pre-run test data reset (not recommended for repeated runs)"
# )

# args = parser.parse_args()

# # ----------------------------------------------------
# # Resolve workflow -> services
# # ----------------------------------------------------

# workflow_name = args.workflow_name or Path(args.k6_script).stem

# if workflow_name in WORKFLOW_CONFIG:
#     services = WORKFLOW_CONFIG[workflow_name]["services"]
# elif args.service:
#     if args.service not in SERVICE_CONFIG:
#         print(f"❌ Unknown service '{args.service}'. Add it to SERVICE_CONFIG first.")
#         sys.exit(1)
#     services = [args.service]
# else:
#     print(
#         f"❌ Workflow '{workflow_name}' not found in WORKFLOW_CONFIG, and no "
#         f"--service fallback was given. Either add '{workflow_name}' to "
#         f"WORKFLOW_CONFIG with its list of services, or pass --service."
#     )
#     sys.exit(1)

# unknown = [s for s in services if s not in SERVICE_CONFIG]
# if unknown:
#     print(f"❌ Workflow '{workflow_name}' references unknown service(s) {unknown}. "
#           "Add them to SERVICE_CONFIG first.")
#     sys.exit(1)

# # ----------------------------------------------------
# # Create experiment folder
# # ----------------------------------------------------

# experiment_dir = (
#     Path("../datasets") / "traces" / args.architecture / args.sampling / workflow_name / f"run{args.run}"
# )
# experiment_dir.mkdir(parents=True, exist_ok=True)

# print(f"\nWorkflow      : {workflow_name}")
# print(f"Services      : {', '.join(services)}")
# print(f"Output folder : {experiment_dir}")

# # ----------------------------------------------------
# # Record experiment start
# # ----------------------------------------------------

# print("=" * 60)
# print("Starting Experiment")
# print("=" * 60)

# start_time = datetime.now(timezone.utc)
# print(f"Start Time : {start_time.isoformat()} UTC")

# before_metrics = collect_all_service_metrics(services)

# # ----------------------------------------------------
# # Run k6
# # ----------------------------------------------------

# print("\nRunning k6...")

# k6_summary = experiment_dir / "k6_summary.json"

# k6_command = [
#     "k6", "run",
#     "--summary-export", str(k6_summary),
#     args.k6_script
# ]

# result = subprocess.run(k6_command)

# if result.returncode != 0:
#     print("\n❌ k6 execution failed.")
#     sys.exit(1)

# print("\nk6 completed successfully.")

# after_metrics = collect_all_service_metrics(services)

# # ----------------------------------------------------
# # Read k6 Summary
# # ----------------------------------------------------

# k6_metrics = read_k6_metrics(k6_summary)

# print("\nPerformance Metrics")
# print(f"Average Response Time : {k6_metrics['response_time_ms']} ms")
# print(f"Throughput            : {k6_metrics['throughput_req_per_sec']} req/s")
# print(f"Failed Requests       : {k6_metrics['failed_requests']}")
# print(f"Total Requests        : {k6_metrics['total_requests']}")

# # ----------------------------------------------------
# # Wait for Jaeger exporter, then compute trace window
# # ----------------------------------------------------

# print(f"\nWaiting {args.wait} seconds for traces...")
# time.sleep(args.wait)

# end_time = datetime.now(timezone.utc)

# start_us = to_jaeger_us(start_time, buffer_seconds=-10)  # catch early spans
# end_us = to_jaeger_us(end_time, buffer_seconds=20)        # catch flushed spans

# experiment_duration = (end_time - start_time).total_seconds()
# print(f"End Time : {end_time.isoformat()} UTC")

# # ----------------------------------------------------
# # Per-service CPU utilization — delta of a cumulative counter,
# # normalized by duration x core count.
# # ----------------------------------------------------

# cpu_count = os.cpu_count()

# per_service_resource_metrics = {}
# for service in services:
#     cpu_used = after_metrics[service]["cpu_seconds"] - before_metrics[service]["cpu_seconds"]
#     cpu_utilization = (
#         (cpu_used / (experiment_duration * cpu_count)) * 100
#         if experiment_duration and cpu_count else 0
#     )
#     per_service_resource_metrics[service] = {
#         "cpu_time_before_seconds": round(before_metrics[service]["cpu_seconds"], 4),
#         "cpu_time_after_seconds": round(after_metrics[service]["cpu_seconds"], 4),
#         "cpu_time_used_seconds": round(cpu_used, 4),
#         "cpu_utilization_percent": round(cpu_utilization, 2),
#         "memory_usage_mb": round(after_metrics[service]["memory_mb"], 2),
#     }

# # ----------------------------------------------------
# # Save experiment info
# # ----------------------------------------------------

# experiment = {
#     "workflow": workflow_name,
#     "architecture": args.architecture,
#     "sampling": args.sampling,
#     "run": args.run,
#     "start_time": start_time.isoformat(),
#     "end_time": end_time.isoformat(),
#     "k6_script": args.k6_script,

#     "performance_metrics": {
#         "average_response_time_ms": k6_metrics["response_time_ms"],
#         "throughput_req_per_sec": k6_metrics["throughput_req_per_sec"],
#         "failed_requests": k6_metrics["failed_requests"],
#         "total_requests": k6_metrics["total_requests"]
#     },

#     "logical_cpu_count": cpu_count,

#     "services": per_service_resource_metrics,

#     "trace_window": {
#         "start_us": start_us,
#         "end_us": end_us
#     }
# }

# experiment_file = experiment_dir / "experiment.json"

# with open(experiment_file, "w") as f:
#     json.dump(experiment, f, indent=4)

# print("\nExperiment metadata saved.")

# # ----------------------------------------------------
# # Call collect_traces.py with the time window and every
# # jaeger service name involved in this workflow
# # ----------------------------------------------------

# print("\nCollecting traces from Jaeger...")

# jaeger_services = ",".join(SERVICE_CONFIG[s]["jaeger_service"] for s in services)

# collect_command = [
#     sys.executable,
#     "collect_traces.py",
#     "--services", jaeger_services,
#     "--architecture", args.architecture,
#     "--sampling", args.sampling,
#     "--workflow", workflow_name,
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

# ============================================================
# Per-service configuration
#
# Add an entry here for every microservice you want metrics from.
# "prometheus_url"  -> the service's Prometheus/Micrometer scrape endpoint
# "jaeger_service"  -> the exact service name it registers under in Jaeger
# ============================================================

SERVICE_CONFIG = {
    "customer": {
        "prometheus_url": "http://localhost:8001/metrics",
        "jaeger_service": "customer-service",
    },
    "products": {
        "prometheus_url": "http://localhost:8002/metrics",
        "jaeger_service": "product-service",
    },
    "shopping": {
        "prometheus_url": "http://localhost:8003/metrics",
        "jaeger_service": "shopping-service",
    },
    # Add more services here as they come online, e.g.:
    # "order": {
    #     "prometheus_url": "http://localhost:8004/metrics",
    #     "jaeger_service": "order-service",
    # },
}

# ============================================================
# Per-workflow configuration
#
# Maps a workflow name (derived from the k6 script filename, or passed
# explicitly via --workflow-name) to the list of services that
# participate in it. Keys in "services" must exist in SERVICE_CONFIG.
# ============================================================

WORKFLOW_CONFIG = {
    "login": {
        "services": ["customer"],
    },
    "signup": {
            "services": ["customer"],
    },
    "customer_workflow": {
        "services": ["customer"],
    },
    "browse_product": {
        "services": ["products"],
    },
    "wishlist_workflow": {
        "services": ["products"],
    },
    "cart_workflow": {
            "services": ["customer", "products", "shopping"],
    },
    "checkout_workflow": {
        "services": ["customer", "products", "shopping"],
    },
    # Add more workflows here, matching your k6 script names, e.g.:
    # "wishlist_workflow": {
    #     "services": ["customer", "products"],
    # },
}


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


def read_node_metrics(url):
    """
    Read cumulative CPU time and resident memory from a service's
    Prometheus endpoint. These services expose Node.js prom-client
    default metrics, e.g.:

        process_cpu_seconds_total       (counter, already in seconds)
        process_resident_memory_bytes   (gauge, RSS)

    (Despite the name, this works for any service exposing these two
    standard prom-client/Prometheus process metrics.)
    """

    response = requests.get(url, timeout=5)
    response.raise_for_status()

    text = response.text

    num = r"([0-9.eE+-]+)"

    # Cumulative CPU-seconds since process start (counter, not a ratio).
    cpu_match = re.search(
        rf"^process_cpu_seconds_total\s+{num}",
        text,
        re.MULTILINE
    )

    memory_match = re.search(
        rf"^process_resident_memory_bytes\s+{num}",
        text,
        re.MULTILINE
    )

    if cpu_match is None:
        print(f"⚠️  process_cpu_seconds_total not found at {url} "
              "— confirm this service exposes default prom-client process metrics.")
        cpu_seconds = 0.0
    else:
        cpu_seconds = float(cpu_match.group(1))

    if memory_match is None:
        print(f"⚠️  process_resident_memory_bytes not found at {url}")
        memory_mb = 0.0
    else:
        memory_bytes = float(memory_match.group(1))
        memory_mb = memory_bytes / (1024 * 1024)

    return {
        "cpu_seconds": cpu_seconds,
        "memory_mb": round(memory_mb, 2)
    }


def collect_all_service_metrics(services):
    """Read Prometheus metrics for every service in the workflow."""
    metrics = {}
    for service in services:
        url = SERVICE_CONFIG[service]["prometheus_url"]
        try:
            metrics[service] = read_node_metrics(url)
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Failed to read metrics for '{service}' at {url}: {e}")
            metrics[service] = {"cpu_seconds": 0.0, "memory_mb": 0.0}
    return metrics


def to_jaeger_us(dt: datetime, buffer_seconds: float = 0) -> int:
    """Convert datetime to microseconds since epoch, Jaeger's expected format."""
    return int((dt.timestamp() + buffer_seconds) * 1_000_000)


# ----------------------------------------------------
# Command-line arguments
# ----------------------------------------------------

parser = argparse.ArgumentParser(description="Run Observability Experiment")

parser.add_argument(
    "--workflow-name",
    default=None,
    help="Workflow name, must match a key in WORKFLOW_CONFIG. If omitted, "
         "it's derived automatically from the k6 script filename "
         "(e.g. checkout_workflow.js -> checkout_workflow)."
)
parser.add_argument(
    "--service",
    default=None,
    help="Fallback: single service name (key in SERVICE_CONFIG) to use if "
         "the workflow isn't found in WORKFLOW_CONFIG."
)
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

args = parser.parse_args()

# ----------------------------------------------------
# Resolve workflow -> services
# ----------------------------------------------------

workflow_name = args.workflow_name or Path(args.k6_script).stem

if workflow_name in WORKFLOW_CONFIG:
    services = WORKFLOW_CONFIG[workflow_name]["services"]
elif args.service:
    if args.service not in SERVICE_CONFIG:
        print(f"❌ Unknown service '{args.service}'. Add it to SERVICE_CONFIG first.")
        sys.exit(1)
    services = [args.service]
else:
    print(
        f"❌ Workflow '{workflow_name}' not found in WORKFLOW_CONFIG, and no "
        f"--service fallback was given. Either add '{workflow_name}' to "
        f"WORKFLOW_CONFIG with its list of services, or pass --service."
    )
    sys.exit(1)

unknown = [s for s in services if s not in SERVICE_CONFIG]
if unknown:
    print(f"❌ Workflow '{workflow_name}' references unknown service(s) {unknown}. "
          "Add them to SERVICE_CONFIG first.")
    sys.exit(1)

# ----------------------------------------------------
# Create experiment folder
# ----------------------------------------------------

experiment_dir = (
    Path("../datasets") / "traces" / args.architecture / args.sampling / workflow_name / f"run{args.run}"
)
experiment_dir.mkdir(parents=True, exist_ok=True)

print(f"\nWorkflow      : {workflow_name}")
print(f"Services      : {', '.join(services)}")
print(f"Output folder : {experiment_dir}")

# ----------------------------------------------------
# Record experiment start
# ----------------------------------------------------

print("=" * 60)
print("Starting Experiment")
print("=" * 60)

start_time = datetime.now(timezone.utc)
print(f"Start Time : {start_time.isoformat()} UTC")

before_metrics = collect_all_service_metrics(services)

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

after_metrics = collect_all_service_metrics(services)

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

start_us = to_jaeger_us(start_time, buffer_seconds=-10)  # catch early spans
end_us = to_jaeger_us(end_time, buffer_seconds=20)        # catch flushed spans

experiment_duration = (end_time - start_time).total_seconds()
print(f"End Time : {end_time.isoformat()} UTC")

# ----------------------------------------------------
# Per-service CPU utilization — delta of a cumulative counter,
# normalized by duration x core count.
# ----------------------------------------------------

cpu_count = os.cpu_count()

per_service_resource_metrics = {}
for service in services:
    cpu_used = after_metrics[service]["cpu_seconds"] - before_metrics[service]["cpu_seconds"]
    cpu_utilization = (
        (cpu_used / (experiment_duration * cpu_count)) * 100
        if experiment_duration and cpu_count else 0
    )
    per_service_resource_metrics[service] = {
        "cpu_time_before_seconds": round(before_metrics[service]["cpu_seconds"], 4),
        "cpu_time_after_seconds": round(after_metrics[service]["cpu_seconds"], 4),
        "cpu_time_used_seconds": round(cpu_used, 4),
        "cpu_utilization_percent": round(cpu_utilization, 2),
        "memory_usage_mb": round(after_metrics[service]["memory_mb"], 2),
    }

# ----------------------------------------------------
# Totals across all services — handy for quick
# apples-to-apples comparisons between runs/architectures.
# ----------------------------------------------------

total_cpu_utilization_percent = round(
    sum(m["cpu_utilization_percent"] for m in per_service_resource_metrics.values()), 2
)
total_memory_usage_mb = round(
    sum(m["memory_usage_mb"] for m in per_service_resource_metrics.values()), 2
)

# ----------------------------------------------------
# Save experiment info
# ----------------------------------------------------

experiment = {
    "workflow": workflow_name,
    "architecture": args.architecture,
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

    "logical_cpu_count": cpu_count,

    "services": per_service_resource_metrics,

    "totals": {
        "cpu_utilization_percent": total_cpu_utilization_percent,
        "memory_usage_mb": total_memory_usage_mb
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
# Call collect_traces.py with the time window and every
# jaeger service name involved in this workflow
# ----------------------------------------------------

print("\nCollecting traces from Jaeger...")

jaeger_services = ",".join(SERVICE_CONFIG[s]["jaeger_service"] for s in services)

collect_command = [
    sys.executable,
    "collect_traces.py",
    "--services", jaeger_services,
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