"""
Compares the static operational inventory (extract_static_inventory.py's
output) against a collected traces.json to answer: what fraction of the
operations the code CAN perform actually show up as spans, at this
sampling ratio?

Uses ijson to stream-parse traces.json since these files can be very
large (hundreds of MB across a full workflow/run capture).

Usage:
    python compute_coverage.py \
        --inventory ../analysis/static_inventory.json \
        --traces ../datasets/traces/monolith/sample100/checkout_workflow/run1/traces.json \
        --out coverage_sample100_checkout_run1.json

Notes on matching:
    - Route layer (static_inventory "route" entries, e.g. "POST /shopping/order")
      match directly against trace operationNames of the same "METHOD /path"
      shape -- this app's Express auto-instrumentation reports route-pattern
      operationNames, so this match is exact/near-exact for static routes.
    - Service layer and repository layer entries (class methods like
      "AddToWishlist") are NOT separately instrumented under
      getNodeAutoInstrumentations() -- only their underlying mongoose/mongodb
      driver calls show up (e.g. "mongoose.customer.findOne"). These are
      reported separately as "observed instead of" rather than matched
      1:1, since there's no reliable name mapping from a repository method
      to the driver call(s) it makes without reading the method body.
"""

import argparse
import json
import re
from pathlib import Path

try:
    import ijson
except ImportError:
    ijson = None

import service_map as service_map_mod


ROUTE_RE = re.compile(r"^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/\S*)$", re.IGNORECASE)


def load_inventory(path):
    """
    Returns (routes, services, repos). Each route entry is either:
      - a plain string "METHOD /path"           (monolith inventories, no "service" key)
      - a (service_short_name, "METHOD /path") tuple (microservices inventories)
    depending on whether the inventory's operations carry a "service" field.
    """
    inv = json.load(open(path))
    is_microservices = any("service" in op for op in inv["operations"])

    if is_microservices:
        routes = [(op.get("service"), op["name"]) for op in inv["operations"] if op["layer"] == "route"]
    else:
        routes = [op["name"] for op in inv["operations"] if op["layer"] == "route"]

    services = [op for op in inv["operations"] if op["layer"] == "service"]
    repos = [op for op in inv["operations"] if op["layer"] == "repository"]
    return routes, services, repos


def stream_trace_operations(path):
    """
    Returns (op_counts, trace_count, span_count, service_op_counts).

    op_counts:          flat "operationName" -> count, ignoring which service
                         emitted it (used for monolith inventories / backward compat).
    service_op_counts:  (jaeger_service_name, operationName) -> count, built from
                         each span's processID -> trace["processes"][processID]["serviceName"].
                         Empty for traces with no "processes" field (shouldn't happen
                         with real Jaeger data, but handled defensively).

    Streams the file rather than loading it fully into memory.
    """
    op_counts = {}
    service_op_counts = {}
    trace_count = 0
    span_count = 0

    def process_trace(trace):
        nonlocal trace_count, span_count
        trace_count += 1
        processes = trace.get("processes", {}) or {}
        for sp in trace.get("spans", []):
            span_count += 1
            name = sp.get("operationName")
            if not name:
                continue
            op_counts[name] = op_counts.get(name, 0) + 1

            proc_id = sp.get("processID")
            svc_name = processes.get(proc_id, {}).get("serviceName") if proc_id else None
            if svc_name:
                key = (svc_name, name)
                service_op_counts[key] = service_op_counts.get(key, 0) + 1

    if ijson is not None:
        with open(path, "rb") as f:
            for trace in ijson.items(f, "item"):
                process_trace(trace)
    else:
        data = json.load(open(path))
        for trace in data:
            process_trace(trace)

    return op_counts, trace_count, span_count, service_op_counts


def classify_op(op):
    if op.startswith("mongoose."):
        return "mongoose"
    if op.startswith("mongodb."):
        return "mongodb"
    if op.startswith("middleware -") or op.startswith("middleware-"):
        return "middleware"
    if op.startswith("request handler -") or op.startswith("request handler-"):
        return "request_handler"
    if ROUTE_RE.match(op):
        return "route"
    return "other"


def main():
    ap = argparse.ArgumentParser(description="Compute static-inventory-vs-traces coverage")
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default=None, help="Free-text label, e.g. 'sample10 / checkout_workflow / run1'")
    ap.add_argument("--service-map", default=None,
                     help="JSON file mapping inventory service names to Jaeger serviceName "
                          "(default: built-in customer/products/shopping mapping). "
                          "Only used for microservices inventories (routes tagged with 'service').")
    args = ap.parse_args()

    routes, services, repos = load_inventory(args.inventory)
    op_counts, trace_count, span_count, service_op_counts = stream_trace_operations(args.traces)
    trace_ops = set(op_counts.keys())

    is_microservices = routes and isinstance(routes[0], tuple)

    if is_microservices:
        svc_map = service_map_mod.load_service_map(args.service_map)
        observed_pairs = set(service_op_counts.keys())

        matched_routes = []
        missing_routes = []
        for inv_service, route_name in routes:
            jaeger_service = svc_map.get(inv_service)
            display = f"[{inv_service}] {route_name}"
            if jaeger_service and (jaeger_service, route_name) in observed_pairs:
                matched_routes.append(display)
            else:
                missing_routes.append(display)
        matched_routes.sort()
        missing_routes.sort()

        # Route ops seen in traces (any service) that don't correspond to any
        # inventory entry once matched by (jaeger_service, operation).
        inventory_pairs = {
            (svc_map.get(inv_service), route_name) for inv_service, route_name in routes
        }
        unexpected_routes = sorted(
            f"[{svc}] {op}" for (svc, op) in observed_pairs
            if ROUTE_RE.match(op) and (svc, op) not in inventory_pairs
        )
    else:
        matched_routes = sorted(r for r in routes if r in trace_ops)
        missing_routes = sorted(r for r in routes if r not in trace_ops)
        trace_route_ops = {op for op in trace_ops if ROUTE_RE.match(op)}
        unexpected_routes = sorted(trace_route_ops - set(routes))

    route_coverage_pct = round(100 * len(matched_routes) / len(routes), 2) if routes else 0.0

    by_class = {}
    for op, count in op_counts.items():
        cls = classify_op(op)
        by_class.setdefault(cls, {})[op] = count

    report = {
        "label": args.label,
        "traces_file": str(args.traces),
        "microservices_mode": is_microservices,
        "trace_count": trace_count,
        "span_count": span_count,
        "route_coverage": {
            "total_static_routes": len(routes),
            "matched": len(matched_routes),
            "missing": len(missing_routes),
            "coverage_percent": route_coverage_pct,
            "matched_routes": matched_routes,
            "missing_routes": missing_routes,
            "unexpected_route_operations_in_traces": unexpected_routes,
        },
        "service_layer": {
            "total_static_service_methods": len(services),
            "directly_instrumented": 0,
            "note": (
                "Service-layer class methods are not given their own spans "
                "by default auto-instrumentation; they're invisible in "
                "traces unless custom spans are added around them."
            ),
        },
        "repository_layer": {
            "total_static_repository_methods": len(repos),
            "directly_instrumented": 0,
            "observed_mongoose_operations": sorted(by_class.get("mongoose", {}).items(), key=lambda x: -x[1]),
            "observed_mongodb_operations": sorted(by_class.get("mongodb", {}).items(), key=lambda x: -x[1]),
            "note": (
                "Repository-layer methods (e.g. specific query methods) aren't "
                "necessarily traced by name; check whether only the underlying "
                "driver/ORM calls they make are visible (e.g. SQL statements, "
                "mongoose/mongodb calls) at query granularity, not method granularity. "
                "This varies by instrumentation library/language -- inspect "
                "'other_span_categories' below to see what actually showed up."
            ),
        },
        "other_span_categories": {
            "middleware_operations": sorted(by_class.get("middleware", {}).items(), key=lambda x: -x[1]),
            "request_handler_operations": sorted(by_class.get("request_handler", {}).items(), key=lambda x: -x[1]),
            "uncategorized_operations": sorted(by_class.get("other", {}).items(), key=lambda x: -x[1]),
        },
    }

    print(json.dumps(
        {k: v for k, v in report.items() if k != "other_span_categories"},
        indent=2,
    ))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report saved to {args.out}")


if __name__ == "__main__":
    main()
