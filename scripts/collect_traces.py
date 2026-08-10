import os
import json
import time
import argparse
import requests
from datetime import datetime, timezone
from statistics import mean

# ============================================================
# Command Line Arguments
# ============================================================

parser = argparse.ArgumentParser(
    description="Collect OpenTelemetry traces from Jaeger across one or more services"
)

parser.add_argument(
    "--services",
    required=True,
    help="Comma-separated list of service names registered in Jaeger "
         "(e.g. 'customer-service,product-service,shopping-service'). "
         "Each is queried separately and results are merged by traceID, "
         "since a single trace can span multiple services."
)

parser.add_argument(
    "--architecture",
    required=True,
    choices=["monolith", "microservices"],
    help="Architecture type"
)

parser.add_argument(
    "--sampling",
    required=True,
    help="Sampling configuration (off, sample100, sample10, sample1)"
)

parser.add_argument(
    "--workflow",
    default="unspecified_workflow",
    help="Workflow name (e.g. checkout, login). Used to keep different "
         "workflows' trace datasets from overwriting each other under the "
         "same architecture/sampling/run combination."
)

parser.add_argument(
    "--run",
    type=int,
    default=1,
    help="Experiment run number"
)

parser.add_argument(
    "--start",
    type=int,
    default=None,
    help="Start timestamp (microseconds since epoch)"
)

parser.add_argument(
    "--end",
    type=int,
    default=None,
    help="End timestamp (microseconds since epoch)"
)

parser.add_argument(
    "--lookback",
    default="1h",
    help="Fallback Jaeger lookback window (used only if --start/--end are omitted)"
)

parser.add_argument(
    "--limit",
    type=int,
    default=10000,
    help="Maximum traces to download per service"
)

parser.add_argument(
    "--timeout",
    type=int,
    default=30,
    help="HTTP timeout (seconds)"
)

parser.add_argument(
    "--retries",
    type=int,
    default=3,
    help="Retry attempts per service"
)

parser.add_argument(
    "--overwrite",
    action="store_true",
    help="Overwrite existing dataset"
)

args = parser.parse_args()

services = [s.strip() for s in args.services.split(",") if s.strip()]

if not services:
    raise ValueError("--services must contain at least one service name")

# ============================================================
# Configuration
# ============================================================

JAEGER_URL = "http://localhost:16686"

dataset_folder = os.path.join(
    "..",
    "datasets",
    "traces",
    args.architecture,
    args.sampling,
    args.workflow,
    f"run{args.run}"
)

os.makedirs(dataset_folder, exist_ok=True)

trace_file = os.path.join(dataset_folder, "traces.json")
metadata_file = os.path.join(dataset_folder, "metadata.json")
summary_file = os.path.join(dataset_folder, "summary.json")

if os.path.exists(trace_file):
    print(f"Existing dataset found. Overwriting {trace_file}...")

# ============================================================
# Build Jaeger Query (shared across all services)
# ============================================================

window_mode = "lookback"
start_ts = args.start
end_ts = args.end

base_query = {"limit": args.limit}

if start_ts is not None and end_ts is not None:
    base_query["start"] = start_ts
    base_query["end"] = end_ts
    window_mode = "explicit"
else:
    base_query["lookback"] = args.lookback

# ============================================================
# Download Traces — once per service, merged by traceID
# ============================================================

print("=" * 60)
print("Connecting to Jaeger")
print("=" * 60)
print(f"Services : {', '.join(services)}")

traces_by_id = {}
per_service_counts = {}

for service in services:

    query = dict(base_query)
    query["service"] = service

    response_json = None
    last_exception = None

    for attempt in range(1, args.retries + 1):
        try:
            response = requests.get(
                f"{JAEGER_URL}/api/traces",
                params=query,
                timeout=args.timeout
            )
            response.raise_for_status()
            response_json = response.json()
            break

        except requests.exceptions.RequestException as e:
            last_exception = e
            print(f"[{service}] Attempt {attempt}/{args.retries} failed...")
            if attempt < args.retries:
                time.sleep(2)

    if response_json is None:
        print(f"⚠️  Skipping '{service}': {last_exception}")
        per_service_counts[service] = 0
        continue

    service_traces = response_json.get("data", [])
    per_service_counts[service] = len(service_traces)

    print(f"[{service}] Downloaded {len(service_traces)} traces")

    for trace in service_traces:
        trace_id = trace.get("traceID")
        if trace_id is None:
            continue
        # A trace spanning multiple services will come back from more than
        # one query above; keep a single merged copy per traceID, combining
        # any spans/processes not already present.
        if trace_id not in traces_by_id:
            traces_by_id[trace_id] = trace
        else:
            existing = traces_by_id[trace_id]

            existing_span_ids = {s.get("spanID") for s in existing.get("spans", [])}
            for span in trace.get("spans", []):
                if span.get("spanID") not in existing_span_ids:
                    existing.setdefault("spans", []).append(span)

            existing.setdefault("processes", {}).update(trace.get("processes", {}))

traces = list(traces_by_id.values())

print(f"\nMerged total: {len(traces)} unique traces across {len(services)} service(s)")

# ============================================================
# Statistics
# ============================================================

span_count = 0
found_services = set()
operations = set()
span_durations = []
trace_ids = []

for trace in traces:

    trace_ids.append(trace.get("traceID"))

    processes = trace.get("processes", {})
    for process in processes.values():
        service = process.get("serviceName")
        if service:
            found_services.add(service)

    spans = trace.get("spans", [])
    span_count += len(spans)

    for span in spans:
        operation = span.get("operationName")
        if operation:
            operations.add(operation)

        duration = span.get("duration")
        if duration is not None:
            span_durations.append(duration)

# ============================================================
# Save Files
# ============================================================

with open(trace_file, "w") as f:
    json.dump(traces, f, indent=4)

trace_size_bytes = os.path.getsize(trace_file)
trace_size_kb = round(trace_size_bytes / 1024, 2)

# ============================================================
# Summary
# ============================================================

summary = {

    "trace_count": len(traces),

    "trace_file_size_kb": trace_size_kb,

    "span_count": span_count,

    "unique_operations": len(operations),

    "operations": sorted(list(operations)),

    "service_count": len(found_services),

    "services": sorted(list(found_services)),

    "average_span_duration_us":
        round(mean(span_durations), 2)
        if span_durations else 0,

    "minimum_span_duration_us":
        min(span_durations)
        if span_durations else 0,

    "maximum_span_duration_us":
        max(span_durations)
        if span_durations else 0
}

# ============================================================
# Metadata
# ============================================================

metadata = {

    "queried_services": services,

    "per_service_trace_counts": per_service_counts,

    "architecture": args.architecture,

    "sampling": args.sampling,

    "workflow": args.workflow,

    "run": args.run,

    "window_mode": window_mode,

    "start_ts_us": start_ts,

    "end_ts_us": end_ts,

    "lookback":
        args.lookback if window_mode == "lookback" else None,

    "trace_count": len(traces),

    "span_count": span_count,

    "unique_operations": len(operations),

    "service_count": len(found_services),

    "collection_time":
        datetime.now(timezone.utc).isoformat(),

    "jaeger_url": JAEGER_URL,

    "limit": args.limit,

    "trace_ids": trace_ids

}

SAMPLING_RATIOS = {
    "off": 0.0,
    "sample1": 0.01,
    "sample10": 0.10,
    "sample100": 1.0,
}
metadata["sampling_ratio"] = SAMPLING_RATIOS.get(args.sampling)
metadata["trace_file_size_kb"] = trace_size_kb

with open(metadata_file, "w") as f:
    json.dump(metadata, f, indent=4)

with open(summary_file, "w") as f:
    json.dump(summary, f, indent=4)

# ============================================================
# Console Output
# ============================================================

print("\n" + "=" * 60)
print("Trace Collection Completed")
print("=" * 60)

print(f"Architecture      : {args.architecture}")
print(f"Queried services  : {', '.join(services)}")
print(f"Sampling          : {args.sampling}")
print(f"Workflow          : {args.workflow}")
print(f"Run               : {args.run}")

print()

print(f"Traces (merged) : {len(traces)}")
print(f"Spans           : {span_count}")
print(f"Operations      : {len(operations)}")
print(f"Services found  : {len(found_services)}")

print()

print("Files Created")
print("--------------------------------")
print(trace_file)
print(metadata_file)
print(summary_file)

print("\nDone.")
