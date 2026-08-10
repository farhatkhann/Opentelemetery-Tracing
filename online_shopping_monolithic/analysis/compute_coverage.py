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


ROUTE_RE = re.compile(r"^(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s+(/\S*)$", re.IGNORECASE)


def load_inventory(path):
    inv = json.load(open(path))
    routes = [op["name"] for op in inv["operations"] if op["layer"] == "route"]
    services = [op for op in inv["operations"] if op["layer"] == "service"]
    repos = [op for op in inv["operations"] if op["layer"] == "repository"]
    return routes, services, repos


def stream_trace_operations(path):
    """
    Returns (operation -> occurrence count) across every span in the file.
    Streams the file rather than loading it fully into memory.
    """
    op_counts = {}
    trace_count = 0
    span_count = 0

    if ijson is not None:
        with open(path, "rb") as f:
            for trace in ijson.items(f, "item"):
                trace_count += 1
                for sp in trace.get("spans", []):
                    span_count += 1
                    name = sp.get("operationName")
                    if name:
                        op_counts[name] = op_counts.get(name, 0) + 1
    else:
        # Fallback for small files / no ijson installed.
        data = json.load(open(path))
        for trace in data:
            trace_count += 1
            for sp in trace.get("spans", []):
                span_count += 1
                name = sp.get("operationName")
                if name:
                    op_counts[name] = op_counts.get(name, 0) + 1

    return op_counts, trace_count, span_count


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
    args = ap.parse_args()

    routes, services, repos = load_inventory(args.inventory)
    op_counts, trace_count, span_count = stream_trace_operations(args.traces)
    trace_ops = set(op_counts.keys())

    matched_routes = sorted(r for r in routes if r in trace_ops)
    missing_routes = sorted(r for r in routes if r not in trace_ops)

    route_coverage_pct = round(100 * len(matched_routes) / len(routes), 2) if routes else 0.0

    by_class = {}
    for op, count in op_counts.items():
        cls = classify_op(op)
        by_class.setdefault(cls, {})[op] = count

    # Route ops seen in traces that are NOT in the static inventory at all
    # (unexpected/extra coverage, or a naming mismatch worth checking).
    trace_route_ops = {op for op in trace_ops if ROUTE_RE.match(op)}
    unexpected_routes = sorted(trace_route_ops - set(routes))

    report = {
        "label": args.label,
        "traces_file": str(args.traces),
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
                "under getNodeAutoInstrumentations(); they're invisible in "
                "traces unless custom spans are added around them."
            ),
        },
        "repository_layer": {
            "total_static_repository_methods": len(repos),
            "directly_instrumented": 0,
            "observed_mongoose_operations": sorted(by_class.get("mongoose", {}).items(), key=lambda x: -x[1]),
            "observed_mongodb_operations": sorted(by_class.get("mongodb", {}).items(), key=lambda x: -x[1]),
            "note": (
                "Repository-layer class methods (e.g. AddToWishlist) aren't "
                "traced by name; only the underlying mongoose/mongodb driver "
                "calls they make are visible, at collection/operation "
                "granularity, not method granularity."
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
