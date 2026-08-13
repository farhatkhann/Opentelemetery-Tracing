# # import os
# # import json
# # import argparse
# # import requests
# # from datetime import datetime

# # # -----------------------------
# # # Command-line arguments
# # # -----------------------------
# # parser = argparse.ArgumentParser(description="Collect traces from Jaeger")

# # parser.add_argument(
# #     "--service",
# #     required=True,
# #     help="Service name registered in Jaeger"
# # )

# # parser.add_argument(
# #     "--architecture",
# #     required=True,
# #     choices=["monolith", "microservices"],
# #     help="Architecture type"
# # )

# # parser.add_argument(
# #     "--sampling",
# #     required=True,
# #     help="Sampling configuration (off, sample100, sample10, sample1)"
# # )

# # parser.add_argument(
# #     "--run",
# #     type=int,
# #     default=1,
# #     help="Experiment run number"
# # )

# # parser.add_argument(
# #     "--lookback",
# #     default="1h",
# #     help="Jaeger lookback window"
# # )

# # parser.add_argument(
# #     "--limit",
# #     type=int,
# #     default=500,
# #     help="Maximum traces to download"
# # )

# # args = parser.parse_args()

# # # -----------------------------
# # # Configuration
# # # -----------------------------
# # JAEGER_URL = "http://localhost:16686"

# # experiment_folder = os.path.join(
# #     "datasets",
# #     "traces",
# #     args.architecture,
# #     args.sampling,
# #     f"run{args.run}"
# # )

# # os.makedirs(experiment_folder, exist_ok=True)

# # # -----------------------------
# # # Download traces
# # # -----------------------------
# # print("Connecting to Jaeger...")

# # response = requests.get(
# #     f"{JAEGER_URL}/api/traces",
# #     params={
# #         "service": args.service,
# #         "lookback": args.lookback,
# #         "limit": args.limit
# #     }
# # )

# # response.raise_for_status()

# # result = response.json()

# # traces = result.get("data", [])

# # print(f"Downloaded {len(traces)} traces")

# # # -----------------------------
# # # Save traces
# # # -----------------------------
# # trace_file = os.path.join(
# #     experiment_folder,
# #     "traces.json"
# # )

# # with open(trace_file, "w") as f:
# #     json.dump(traces, f, indent=4)

# # # -----------------------------
# # # Metadata
# # # -----------------------------
# # metadata = {
# #     "service_name": args.service,
# #     "architecture": args.architecture,
# #     "sampling": args.sampling,
# #     "run": args.run,
# #     "lookback": args.lookback,
# #     "trace_count": len(traces),
# #     "collection_time": datetime.now().isoformat(),
# #     "jaeger_url": JAEGER_URL
# # }

# # metadata_file = os.path.join(
# #     experiment_folder,
# #     "metadata.json"
# # )

# # with open(metadata_file, "w") as f:
# #     json.dump(metadata, f, indent=4)

# # print("\nDataset saved successfully!")

# # print(f"Folder : {experiment_folder}")
# # print(f"Traces : {trace_file}")
# # print(f"Metadata : {metadata_file}")

# import os
# import json
# import time
# import argparse
# import requests
# from datetime import datetime, timezone
# from statistics import mean

# # ============================================================
# # Command Line Arguments
# # ============================================================

# parser = argparse.ArgumentParser(
#     description="Collect OpenTelemetry traces from Jaeger"
# )

# parser.add_argument(
#     "--service",
#     required=True,
#     help="Service name registered in Jaeger"
# )

# parser.add_argument(
#     "--architecture",
#     required=True,
#     choices=["monolith", "microservices"],
#     help="Architecture type"
# )

# parser.add_argument(
#     "--sampling",
#     required=True,
#     help="Sampling configuration (off, sample100, sample10, sample1)"
# )

# parser.add_argument(
#     "--run",
#     type=int,
#     default=1,
#     help="Experiment run number"
# )

# parser.add_argument(
#     "--start",
#     type=int,
#     default=None,
#     help="Start timestamp (microseconds since epoch)"
# )

# parser.add_argument(
#     "--end",
#     type=int,
#     default=None,
#     help="End timestamp (microseconds since epoch)"
# )

# parser.add_argument(
#     "--lookback",
#     default="1h",
#     help="Fallback Jaeger lookback window"
# )

# parser.add_argument(
#     "--limit",
#     type=int,
#     default=1000000,
#     help="Maximum traces to download"
# )

# parser.add_argument(
#     "--timeout",
#     type=int,
#     default=30,
#     help="HTTP timeout (seconds)"
# )

# parser.add_argument(
#     "--retries",
#     type=int,
#     default=3,
#     help="Retry attempts"
# )

# parser.add_argument(
#     "--overwrite",
#     action="store_true",
#     help="Overwrite existing dataset"
# )

# args = parser.parse_args()

# # ============================================================
# # Configuration
# # ============================================================

# JAEGER_URL = "http://localhost:16686"

# dataset_folder = os.path.join(
#     "..",
#     "datasets",
#     "traces",
#     args.architecture,
#     args.sampling,
#     f"run{args.run}"
# )

# os.makedirs(dataset_folder, exist_ok=True)

# trace_file = os.path.join(dataset_folder, "traces.json")
# metadata_file = os.path.join(dataset_folder, "metadata.json")
# summary_file = os.path.join(dataset_folder, "summary.json")

# if os.path.exists(trace_file):
#     print(f"Existing dataset found. Overwriting {trace_file}...")

# # ============================================================
# # Build Jaeger Query
# # ============================================================

# query = {
#     "service": args.service,
#     "limit": args.limit
# }

# window_mode = "lookback"

# start_ts = args.start
# end_ts = args.end

# if start_ts is not None and end_ts is not None:

#     query["start"] = start_ts
#     query["end"] = end_ts

#     window_mode = "explicit"

# else:

#     query["lookback"] = args.lookback

# # ============================================================
# # Download Traces
# # ============================================================

# print("=" * 60)
# print("Connecting to Jaeger")
# print("=" * 60)

# response_json = None
# last_exception = None

# for attempt in range(1, args.retries + 1):

#     try:

#         response = requests.get(
#             f"{JAEGER_URL}/api/traces",
#             params=query,
#             timeout=args.timeout
#         )

#         response.raise_for_status()

#         response_json = response.json()

#         break

#     except requests.exceptions.RequestException as e:

#         last_exception = e

#         print(
#             f"Attempt {attempt}/{args.retries} failed..."
#         )

#         if attempt < args.retries:
#             time.sleep(2)

# if response_json is None:
#     raise RuntimeError(last_exception)

# traces = response_json.get("data", [])

# print(f"\nDownloaded {len(traces)} traces")

# # ============================================================
# # Statistics
# # ============================================================

# span_count = 0

# services = set()

# operations = set()

# span_durations = []

# trace_ids = []

# for trace in traces:

#     trace_ids.append(trace.get("traceID"))

#     processes = trace.get("processes", {})

#     for process in processes.values():

#         service = process.get("serviceName")

#         if service:
#             services.add(service)

#     spans = trace.get("spans", [])

#     span_count += len(spans)

#     for span in spans:

#         operation = span.get("operationName")

#         if operation:
#             operations.add(operation)

#         duration = span.get("duration")

#         if duration is not None:
#             span_durations.append(duration)

# # ============================================================
# # Save Files
# # ============================================================

# with open(trace_file, "w") as f:
#     json.dump(traces, f, indent=4)

# trace_size_bytes = os.path.getsize(trace_file)

# trace_size_kb = round(
#     trace_size_bytes / 1024,
#     2
# )

# # ============================================================
# # Summary
# # ============================================================

# summary = {

#     "trace_count": len(traces),

#     "trace_file_size_kb": trace_size_kb,

#     "span_count": span_count,

#     "unique_operations": len(operations),

#     "operations": sorted(list(operations)),

#     "service_count": len(services),

#     "services": sorted(list(services)),

#     "average_span_duration_us":
#         round(mean(span_durations), 2)
#         if span_durations else 0,

#     "minimum_span_duration_us":
#         min(span_durations)
#         if span_durations else 0,

#     "maximum_span_duration_us":
#         max(span_durations)
#         if span_durations else 0
# }

# # ============================================================
# # Metadata
# # ============================================================

# metadata = {

#     "service_name": args.service,

#     "architecture": args.architecture,

#     "sampling": args.sampling,

#     "run": args.run,

#     "window_mode": window_mode,

#     "start_ts_us": start_ts,

#     "end_ts_us": end_ts,

#     "lookback":
#         args.lookback if window_mode == "lookback" else None,

#     "trace_count": len(traces),

#     "span_count": span_count,

#     "unique_operations": len(operations),

#     "service_count": len(services),

#     "collection_time":
#         datetime.now(timezone.utc).isoformat(),

#     "jaeger_url": JAEGER_URL,

#     "limit": args.limit,

#     "trace_ids": trace_ids

# }

# SAMPLING_RATIOS = {
#     "off": 0.0,
#     "sample1": 0.01,
#     "sample10": 0.10,
#     "sample100": 1.0,
# }
# metadata["sampling_ratio"] = SAMPLING_RATIOS.get(args.sampling)
# metadata["trace_file_size_kb"] = trace_size_kb

# with open(metadata_file, "w") as f:
#     json.dump(metadata, f, indent=4)

# with open(summary_file, "w") as f:
#     json.dump(summary, f, indent=4)

# # ============================================================
# # Console Output
# # ============================================================

# print("\n" + "=" * 60)
# print("Trace Collection Completed")
# print("=" * 60)

# print(f"Architecture : {args.architecture}")
# print(f"Service      : {args.service}")
# print(f"Sampling     : {args.sampling}")
# print(f"Run          : {args.run}")

# print()

# print(f"Traces        : {len(traces)}")
# print(f"Spans         : {span_count}")
# print(f"Operations    : {len(operations)}")
# print(f"Services      : {len(services)}")

# print()

# print("Files Created")

# print("--------------------------------")

# print(trace_file)
# print(metadata_file)
# print(summary_file)

# print("\nDone.")

# import os
# import json
# import time
# import argparse
# import requests
# from datetime import datetime, timezone
# from statistics import mean

# # ============================================================
# # Command Line Arguments
# # ============================================================

# parser = argparse.ArgumentParser(
#     description="Collect OpenTelemetry traces from Jaeger"
# )

# parser.add_argument(
#     "--service",
#     required=True,
#     help="Service name registered in Jaeger"
# )

# parser.add_argument(
#     "--architecture",
#     required=True,
#     choices=["monolith", "microservices"],
#     help="Architecture type"
# )

# parser.add_argument(
#     "--sampling",
#     required=True,
#     help="Sampling configuration (off, sample100, sample10, sample1)"
# )

# parser.add_argument(
#     "--run",
#     type=int,
#     default=1,
#     help="Experiment run number"
# )

# parser.add_argument(
#     "--start",
#     type=int,
#     default=None,
#     help="Start timestamp (microseconds since epoch)"
# )

# parser.add_argument(
#     "--end",
#     type=int,
#     default=None,
#     help="End timestamp (microseconds since epoch)"
# )

# parser.add_argument(
#     "--lookback",
#     default="1h",
#     help="Fallback Jaeger lookback window"
# )

# parser.add_argument(
#     "--limit",
#     type=int,
#     default=100000,
#     help="Maximum traces to download"
# )

# parser.add_argument(
#     "--timeout",
#     type=int,
#     default=30,
#     help="HTTP timeout (seconds)"
# )

# parser.add_argument(
#     "--retries",
#     type=int,
#     default=3,
#     help="Retry attempts"
# )

# parser.add_argument(
#     "--overwrite",
#     action="store_true",
#     help="Overwrite existing dataset"
# )

# args = parser.parse_args()

# # ============================================================
# # Configuration
# # ============================================================

# JAEGER_URL = "http://localhost:16686"

# dataset_folder = os.path.join(
#     "..",
#     "datasets",
#     "traces",
#     args.architecture,
#     args.sampling,
#     f"run{args.run}"
# )

# os.makedirs(dataset_folder, exist_ok=True)

# trace_file = os.path.join(dataset_folder, "traces.json")
# metadata_file = os.path.join(dataset_folder, "metadata.json")
# summary_file = os.path.join(dataset_folder, "summary.json")

# if os.path.exists(trace_file):
#     print(f"Existing dataset found. Overwriting {trace_file}...")

# # ============================================================
# # Build Jaeger Query
# # ============================================================

# query = {
#     "service": args.service,
#     "limit": args.limit
# }

# window_mode = "lookback"

# start_ts = args.start
# end_ts = args.end

# if start_ts is not None and end_ts is not None:

#     query["start"] = start_ts
#     query["end"] = end_ts

#     window_mode = "explicit"

# else:

#     query["lookback"] = args.lookback

# # ============================================================
# # Download Traces
# # ============================================================

# print("=" * 60)
# print("Connecting to Jaeger")
# print("=" * 60)

# response_json = None
# last_exception = None

# for attempt in range(1, args.retries + 1):

#     try:

#         response = requests.get(
#             f"{JAEGER_URL}/api/traces",
#             params=query,
#             timeout=args.timeout
#         )

#         response.raise_for_status()

#         response_json = response.json()

#         break

#     except requests.exceptions.RequestException as e:

#         last_exception = e

#         print(
#             f"Attempt {attempt}/{args.retries} failed..."
#         )

#         if attempt < args.retries:
#             time.sleep(2)

# if response_json is None:
#     raise RuntimeError(last_exception)

# traces = response_json.get("data", [])

# print(f"\nDownloaded {len(traces)} traces")

# # ============================================================
# # Statistics
# # ============================================================

# span_count = 0

# services = set()

# operations = set()

# span_durations = []

# trace_ids = []

# for trace in traces:

#     trace_ids.append(trace.get("traceID"))

#     processes = trace.get("processes", {})

#     for process in processes.values():

#         service = process.get("serviceName")

#         if service:
#             services.add(service)

#     spans = trace.get("spans", [])

#     span_count += len(spans)

#     for span in spans:

#         operation = span.get("operationName")

#         if operation:
#             operations.add(operation)

#         duration = span.get("duration")

#         if duration is not None:
#             span_durations.append(duration)

# # ============================================================
# # Save Files
# # ============================================================

# with open(trace_file, "w") as f:
#     json.dump(traces, f, indent=4)

# trace_size_bytes = os.path.getsize(trace_file)

# trace_size_kb = round(
#     trace_size_bytes / 1024,
#     2
# )

# # ============================================================
# # Summary
# # ============================================================

# summary = {

#     "trace_count": len(traces),

#     "trace_file_size_kb": trace_size_kb,

#     "span_count": span_count,

#     "unique_operations": len(operations),

#     "operations": sorted(list(operations)),

#     "service_count": len(services),

#     "services": sorted(list(services)),

#     "average_span_duration_us":
#         round(mean(span_durations), 2)
#         if span_durations else 0,

#     "minimum_span_duration_us":
#         min(span_durations)
#         if span_durations else 0,

#     "maximum_span_duration_us":
#         max(span_durations)
#         if span_durations else 0
# }

# # ============================================================
# # Metadata
# # ============================================================

# metadata = {

#     "service_name": args.service,

#     "architecture": args.architecture,

#     "sampling": args.sampling,

#     "run": args.run,

#     "window_mode": window_mode,

#     "start_ts_us": start_ts,

#     "end_ts_us": end_ts,

#     "lookback":
#         args.lookback if window_mode == "lookback" else None,

#     "trace_count": len(traces),

#     "span_count": span_count,

#     "unique_operations": len(operations),

#     "service_count": len(services),

#     "collection_time":
#         datetime.now(timezone.utc).isoformat(),

#     "jaeger_url": JAEGER_URL,

#     "limit": args.limit,

#     "trace_ids": trace_ids

# }

# SAMPLING_RATIOS = {
#     "off": 0.0,
#     "sample1": 0.01,
#     "sample10": 0.10,
#     "sample100": 1.0,
# }
# metadata["sampling_ratio"] = SAMPLING_RATIOS.get(args.sampling)
# metadata["trace_file_size_kb"] = trace_size_kb

# with open(metadata_file, "w") as f:
#     json.dump(metadata, f, indent=4)

# with open(summary_file, "w") as f:
#     json.dump(summary, f, indent=4)

# # ============================================================
# # Console Output
# # ============================================================

# print("\n" + "=" * 60)
# print("Trace Collection Completed")
# print("=" * 60)

# print(f"Architecture : {args.architecture}")
# print(f"Service      : {args.service}")
# print(f"Sampling     : {args.sampling}")
# print(f"Run          : {args.run}")

# print()

# print(f"Traces        : {len(traces)}")
# print(f"Spans         : {span_count}")
# print(f"Operations    : {len(operations)}")
# print(f"Services      : {len(services)}")

# print()

# print("Files Created")

# print("--------------------------------")

# print(trace_file)
# print(metadata_file)
# print(summary_file)

# print("\nDone.")

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
    description="Collect OpenTelemetry traces from Jaeger"
)

parser.add_argument(
    "--service",
    required=True,
    help="Service name registered in Jaeger"
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
    "--run",
    type=int,
    default=1,
    help="Experiment run number"
)

parser.add_argument(
    "--workflow",
    default="unspecified_workflow",
    help="Workflow name (e.g. wishlist_workflow, cart_workflow). Used to "
         "keep different workflows' trace datasets from overwriting each "
         "other under the same architecture/sampling/run combination."
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
    help="Fallback Jaeger lookback window"
)

parser.add_argument(
    "--limit",
    type=int,
    default=10000,
    help="Maximum traces to download"
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
    help="Retry attempts"
)

parser.add_argument(
    "--overwrite",
    action="store_true",
    help="Overwrite existing dataset"
)

args = parser.parse_args()

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
# Build Jaeger Query
# ============================================================

query = {
    "service": args.service,
    "limit": args.limit
}

window_mode = "lookback"

start_ts = args.start
end_ts = args.end

if start_ts is not None and end_ts is not None:

    query["start"] = start_ts
    query["end"] = end_ts

    window_mode = "explicit"

else:

    query["lookback"] = args.lookback

# ============================================================
# Download Traces
# ============================================================

print("=" * 60)
print("Connecting to Jaeger")
print("=" * 60)

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

        print(
            f"Attempt {attempt}/{args.retries} failed..."
        )

        if attempt < args.retries:
            time.sleep(2)

if response_json is None:
    raise RuntimeError(last_exception)

traces = response_json.get("data", [])

print(f"\nDownloaded {len(traces)} traces")

# ============================================================
# Statistics
# ============================================================

span_count = 0

services = set()

operations = set()

span_durations = []

trace_ids = []

for trace in traces:

    trace_ids.append(trace.get("traceID"))

    processes = trace.get("processes", {})

    for process in processes.values():

        service = process.get("serviceName")

        if service:
            services.add(service)

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

trace_size_kb = round(
    trace_size_bytes / 1024,
    2
)

# ============================================================
# Summary
# ============================================================

summary = {

    "trace_count": len(traces),

    "trace_file_size_kb": trace_size_kb,

    "span_count": span_count,

    "unique_operations": len(operations),

    "operations": sorted(list(operations)),

    "service_count": len(services),

    "services": sorted(list(services)),

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

    "service_name": args.service,

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

    "service_count": len(services),

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

print(f"Architecture : {args.architecture}")
print(f"Service      : {args.service}")
print(f"Sampling     : {args.sampling}")
print(f"Workflow     : {args.workflow}")
print(f"Run          : {args.run}")

print()

print(f"Traces        : {len(traces)}")
print(f"Spans         : {span_count}")
print(f"Operations    : {len(operations)}")
print(f"Services      : {len(services)}")

print()

print("Files Created")

print("--------------------------------")

print(trace_file)
print(metadata_file)
print(summary_file)

print("\nDone.")