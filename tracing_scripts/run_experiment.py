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
# # "prometheus_url" -> the service's Spring Boot Actuator Prometheus scrape
# #                      endpoint. Ports below match the default docker-compose.yml
# #                      in spring-petclinic/spring-petclinic-microservices.
# # "jaeger_service"  -> the exact service name it registers under in Jaeger
# # ============================================================

# SERVICE_CONFIG = {
#     "gateway": {
#         "prometheus_url": "http://localhost:8080/actuator/prometheus",
#         "jaeger_service": "api-gateway",
#     },
#     "customers": {
#         "prometheus_url": "http://localhost:8081/actuator/prometheus",
#         "jaeger_service": "customers-service",
#     },
#     "visits": {
#         "prometheus_url": "http://localhost:8082/actuator/prometheus",
#         "jaeger_service": "visits-service",
#     },
#     "vets": {
#         "prometheus_url": "http://localhost:8083/actuator/prometheus",
#         "jaeger_service": "vets-service",
#     },
#     # genai-service doesn't publish a host port in the default docker-compose.yml.
#     # Add it here (with its actuator URL and Jaeger service name) if you expose one:
#     # "genai": {
#     #     "prometheus_url": "http://localhost:8084/actuator/prometheus",
#     #     "jaeger_service": "genai-service",
#     # },
# }

# # ============================================================
# # Per-workflow configuration
# #
# # Maps a workflow name (derived from the k6 script filename, or passed
# # explicitly via --workflow-name) to the list of services that
# # participate in it. Keys in "services" must exist in SERVICE_CONFIG.
# #
# # Adjust these to match what each k6 script actually calls -- these are
# # reasonable defaults based on the petclinic API surface (owners/pets live
# # in customers-service, visits in visits-service, vet listings in
# # vets-service; api-gateway fronts all of them).
# # ============================================================

# WORKFLOW_CONFIG = {
#     "browseOwners": {
#         "services": ["gateway", "customers"],
#     },
#     "ownerRegistration": {
#         "services": ["gateway", "customers"],
#     },
#     "ownerUpdate": {
#         "services": ["gateway", "customers"],
#     },
#     "petRegistration": {
#         "services": ["gateway", "customers"],
#     },
#     "visitRegistration": {
#         "services": ["gateway", "customers", "visits"],
#     },
#     "mixedWorkflow": {
#         "services": ["gateway", "customers", "vets", "visits"],
#     },
#     # Add more workflows here, matching your k6 script names, e.g.:
#     # "vetBrowsing": {
#     #     "services": ["gateway", "vets"],
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
#     Read cumulative CPU time and total JVM memory from a Spring Boot
#     service's Actuator Prometheus endpoint.

#     NOTE: process_cpu_time_ns_total requires the custom
#     ProcessCpuTimeMetricConfig bean (see ProcessCpuTimeMetricConfig.java)
#     to be registered in *each* service you scrape here.
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
#               "— is ProcessCpuTimeMetricConfig registered in this service?")
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
#     """Read Actuator/Prometheus metrics for every service in the workflow."""
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
#          "(e.g. browseOwners.js -> browseOwners)."
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
# # Totals across all services — handy for quick
# # apples-to-apples comparisons between runs/architectures.
# # ----------------------------------------------------

# total_cpu_utilization_percent = round(
#     sum(m["cpu_utilization_percent"] for m in per_service_resource_metrics.values()), 2
# )
# total_memory_usage_mb = round(
#     sum(m["memory_usage_mb"] for m in per_service_resource_metrics.values()), 2
# )

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

#     "totals": {
#         "cpu_utilization_percent": total_cpu_utilization_percent,
#         "memory_usage_mb": total_memory_usage_mb
#     },

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
# "prometheus_url" -> the service's Spring Boot Actuator Prometheus scrape
#                      endpoint. Ports below match the default docker-compose.yml
#                      in spring-petclinic/spring-petclinic-microservices.
# "jaeger_service"  -> the exact service name it registers under in Jaeger
# ============================================================

SERVICE_CONFIG = {
    "gateway": {
        "prometheus_url": "http://localhost:8080/actuator/prometheus",
        "jaeger_service": "api-gateway",
    },
    "customers": {
        "prometheus_url": "http://localhost:8081/actuator/prometheus",
        "jaeger_service": "customers-service",
    },
    "visits": {
        "prometheus_url": "http://localhost:8082/actuator/prometheus",
        "jaeger_service": "visits-service",
    },
    "vets": {
        "prometheus_url": "http://localhost:8083/actuator/prometheus",
        "jaeger_service": "vets-service",
    },
    # genai-service doesn't publish a host port in the default docker-compose.yml.
    # Add it here (with its actuator URL and Jaeger service name) if you expose one:
    # "genai": {
    #     "prometheus_url": "http://localhost:8084/actuator/prometheus",
    #     "jaeger_service": "genai-service",
    # },
}

# ============================================================
# Per-workflow configuration
#
# Maps a workflow name (derived from the k6 script filename, or passed
# explicitly via --workflow-name) to the list of services that
# participate in it. Keys in "services" must exist in SERVICE_CONFIG.
#
# Adjust these to match what each k6 script actually calls -- these are
# reasonable defaults based on the petclinic API surface (owners/pets live
# in customers-service, visits in visits-service, vet listings in
# vets-service; api-gateway fronts all of them).
# ============================================================

WORKFLOW_CONFIG = {
    "browseOwners": {
        "services": ["gateway", "customers"],
    },
    "ownerRegistration": {
        "services": ["gateway", "customers"],
    },
    "ownerUpdate": {
        "services": ["gateway", "customers"],
    },
    "petRegistration": {
        "services": ["gateway", "customers"],
    },
    "visitRegistration": {
        "services": ["gateway", "customers", "visits"],
    },
    "mixedWorkflow": {
        "services": ["gateway", "customers", "vets", "visits"],
    },
    # Add more workflows here, matching your k6 script names, e.g.:
    # "vetBrowsing": {
    #     "services": ["gateway", "vets"],
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


def read_node_metrics(url, timeout=15):
    """
    Read instantaneous CPU usage and total JVM memory from a Spring Boot
    service's Actuator Prometheus endpoint.

    process_cpu_usage is exposed automatically by spring-boot-starter-actuator
    + micrometer-registry-prometheus -- no custom bean required. It's a
    ratio (0.0-1.0) representing recent CPU usage *at the moment scraped*,
    not a cumulative counter, so we can't do a before/after delta the way
    a counter-based metric would allow. We sample it before and after the
    k6 run and average the two as a rough estimate of utilization during
    the test -- less precise than continuous sampling across the run, but
    requires no rebuild of the service images.

    timeout defaults to 15s (not k6's own request timeout) because the
    "after" scrape can land while the service's Tomcat thread pool is
    still draining a backlog from the just-finished load test -- the
    Prometheus scrape request has to queue behind those in-flight
    requests, and a short 5s timeout can trip before it gets a thread.
    """

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    text = response.text

    num = r"([0-9.eE+-]+)"

    cpu_match = re.search(
        rf'^process_cpu_time_ns_total(?:\{{.*?\}})?\s+{num}',
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
        print(f"⚠️  process_cpu_time_ns_total not found at {url} "
              "— confirm actuator/prometheus is exposed and reachable.")
        cpu_usage_ratio = 0.0
    else:
        cpu_usage_ratio = float(cpu_match.group(1))

    heap_bytes = sum(float(x) for x in heap_matches)
    nonheap_bytes = sum(float(x) for x in nonheap_matches)
    memory_mb = (heap_bytes + nonheap_bytes) / (1024 * 1024)

    return {
        "cpu_usage_ratio": cpu_usage_ratio,
        "memory_mb": round(memory_mb, 2)
    }


def collect_all_service_metrics(services, retries=3, timeout=15, retry_delay=3):
    """
    Read Actuator/Prometheus metrics for every service in the workflow.

    Retries with a short delay before giving up -- right after a load test
    the service may still be draining a request backlog, so a single failed
    attempt doesn't necessarily mean the endpoint is unreachable, just busy.
    """
    metrics = {}
    for service in services:
        url = SERVICE_CONFIG[service]["prometheus_url"]
        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                metrics[service] = read_node_metrics(url, timeout=timeout)
                last_exception = None
                break
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < retries:
                    print(f"⚠️  [{service}] metrics scrape attempt {attempt}/{retries} "
                          f"failed ({e}); retrying in {retry_delay}s...")
                    time.sleep(retry_delay)

        if last_exception is not None:
            print(f"⚠️  Failed to read metrics for '{service}' at {url} "
                  f"after {retries} attempts: {last_exception}")
            metrics[service] = {"cpu_usage_ratio": 0.0, "memory_mb": 0.0}

    return metrics


def wait_for_eureka_registration(services, discovery_url="http://localhost:8761", max_wait=60, poll_interval=3):
    """
    Poll discovery-server's Eureka REST API until every service in this
    workflow shows status UP, before launching k6.

    This closes a startup race: docker-compose's depends_on only guarantees
    container start order (and only enforces health *if* a healthcheck is
    defined -- customers-service/api-gateway currently have none in this
    compose file). None of that guarantees the Spring Boot app inside has
    finished booting, registered with Eureka, AND had that registration
    propagate into api-gateway's client-side LoadBalancer cache (which
    refreshes on its own ~30s cycle). If k6 starts before that finishes,
    the gateway logs "No servers available for service: X" and every
    request in that window fails instantly (503s), independent of any
    real capacity issue.

    Uses each service's jaeger_service name (e.g. "customers-service")
    since that matches Eureka's registered app id (case-insensitively).
    """
    print(f"\nWaiting for services to register with Eureka (up to {max_wait}s)...")
    deadline = time.time() + max_wait
    pending = {SERVICE_CONFIG[s]["jaeger_service"] for s in services}

    while pending and time.time() < deadline:
        for app_name in list(pending):
            eureka_url = f"{discovery_url}/eureka/apps/{app_name.upper()}"
            try:
                response = requests.get(
                    eureka_url,
                    headers={"Accept": "application/json"},
                    timeout=5,
                )
                if response.ok:
                    data = response.json()
                    instances = data.get("application", {}).get("instance", [])
                    if not isinstance(instances, list):
                        instances = [instances]
                    if any(inst.get("status") == "UP" for inst in instances):
                        print(f"  ✓ {app_name} registered and UP")
                        pending.discard(app_name)
            except (requests.exceptions.RequestException, ValueError):
                pass  # not registered yet / discovery-server still starting

        if pending:
            time.sleep(poll_interval)

    if pending:
        print(f"  ⚠️  Still not confirmed UP in Eureka after {max_wait}s: "
              f"{', '.join(sorted(pending))} (continuing anyway -- expect "
              f"early 'No servers available' failures if these are the "
              f"services this workflow calls)")


def wait_for_service_recovery(services, max_wait=30, poll_interval=3):
    """
    Poll each service's /actuator/health endpoint until it reports UP (or
    max_wait is reached) before scraping "after" metrics or starting the
    next experiment. A load test can leave a service's thread pool draining
    a backlog for several seconds after k6 exits; scraping (or re-running
    k6) immediately can hit that backlog and either time out (see
    read_node_metrics) or start the next run already congested.
    """
    print(f"\nWaiting for services to recover (up to {max_wait}s)...")
    deadline = time.time() + max_wait
    pending = set(services)

    while pending and time.time() < deadline:
        for service in list(pending):
            health_url = SERVICE_CONFIG[service]["prometheus_url"].replace(
                "/actuator/prometheus", "/actuator/health"
            )
            try:
                response = requests.get(health_url, timeout=3)
                if response.ok and response.json().get("status") == "UP":
                    print(f"  ✓ {service} recovered")
                    pending.discard(service)
            except requests.exceptions.RequestException:
                pass  # still recovering / not yet reachable

        if pending:
            time.sleep(poll_interval)

    if pending:
        print(f"  ⚠️  Still not confirmed healthy after {max_wait}s: "
              f"{', '.join(sorted(pending))} (continuing anyway)")


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
         "(e.g. browseOwners.js -> browseOwners)."
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
    "--recovery-wait",
    type=int,
    default=30,
    help="Max seconds to poll service health after k6 finishes, before "
         "scraping 'after' metrics (0 disables the recovery wait)"
)
parser.add_argument(
    "--discovery-wait",
    type=int,
    default=60,
    help="Max seconds to poll discovery-server (Eureka) for this "
         "workflow's services to register before launching k6 (0 disables)"
)
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

if args.discovery_wait > 0:
    wait_for_eureka_registration(services, max_wait=args.discovery_wait)

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

if args.recovery_wait > 0:
    wait_for_service_recovery(services, max_wait=args.recovery_wait)

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
# Per-service CPU utilization — process_cpu_usage is a snapshot ratio, not
# a cumulative counter, so we average the before/after samples instead of
# taking a delta. This is a rough estimate (two point-in-time samples
# bracketing the run), not a true time-integrated average across the test.
# ----------------------------------------------------

cpu_count = os.cpu_count()

per_service_resource_metrics = {}
for service in services:
    before_pct = before_metrics[service]["cpu_usage_ratio"] * 100
    after_pct = after_metrics[service]["cpu_usage_ratio"] * 100
    avg_pct = (before_pct + after_pct) / 2

    per_service_resource_metrics[service] = {
        "cpu_usage_before_percent": round(before_pct, 2),
        "cpu_usage_after_percent": round(after_pct, 2),
        "cpu_utilization_percent": round(avg_pct, 2),
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