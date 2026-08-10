"""
Checks context propagation quality within a traces.json: for each trace,
does every non-root span have a valid CHILD_OF parent that actually exists
within the same trace? Are there unexpected multiple roots (a sign that an
async boundary, or a service-to-service HTTP call, lost the active context
and started an orphaned span tree instead of continuing the request's
trace)?

In a monolith (single process), propagation happens via AsyncLocalStorage
internally, so "broken propagation" shows up as: spans referencing a
parent spanID that isn't in the trace, or a trace with more than one root
span (multiple spans with no CHILD_OF reference at all).

In microservices, this same check ALSO covers the more important case:
does the W3C traceparent header actually survive a real network hop
between services (e.g. shopping-service calling product-service)? This
script additionally reports, per trace, how many distinct Jaeger
serviceNames appear (via trace["processes"]) -- traces spanning >1 service
are direct evidence that context propagation across the network is
working; traces that "should" be cross-service (per your journey/service
architecture) but only ever show one serviceName are a sign propagation
silently failed and a new root trace was started downstream instead.

Usage:
    python check_context_propagation.py \
        --traces ../datasets/traces/monolith/sample10/checkout_workflow/run1/traces.json \
        --out propagation_sample10_checkout_run1.json
"""

import argparse
import json

try:
    import ijson
except ImportError:
    ijson = None


def analyze(path, max_examples=10):
    total_traces = 0
    total_spans = 0
    single_span_traces = 0
    traces_with_broken_refs = 0
    traces_with_multiple_roots = 0
    traces_with_zero_roots = 0
    total_orphan_spans = 0

    # Cross-service propagation tracking (meaningful once traces span >1
    # process; harmless no-op for single-process/monolith traces where
    # every trace will simply show service_count == 1).
    traces_spanning_multiple_services = 0
    service_count_histogram = {}  # e.g. {1: 900, 2: 95, 3: 5}

    broken_examples = []
    multi_root_examples = []
    cross_service_examples = []

    def process(trace):
        nonlocal total_traces, total_spans, single_span_traces
        nonlocal traces_with_broken_refs, traces_with_multiple_roots
        nonlocal traces_with_zero_roots, total_orphan_spans
        nonlocal traces_spanning_multiple_services

        total_traces += 1
        spans = trace.get("spans", [])
        total_spans += len(spans)

        if len(spans) == 1:
            single_span_traces += 1

        span_ids = {s["spanID"] for s in spans}
        roots = 0
        orphan_count = 0

        for s in spans:
            refs = s.get("references") or []
            child_of = [r for r in refs if r.get("refType") == "CHILD_OF"]
            if not child_of:
                roots += 1
            else:
                for r in child_of:
                    if r.get("spanID") not in span_ids:
                        orphan_count += 1
                        break

        if orphan_count > 0:
            traces_with_broken_refs += 1
            total_orphan_spans += orphan_count
            if len(broken_examples) < max_examples:
                broken_examples.append({
                    "traceID": trace.get("traceID"),
                    "orphan_span_count": orphan_count,
                    "total_spans": len(spans),
                })

        if roots > 1:
            traces_with_multiple_roots += 1
            if len(multi_root_examples) < max_examples:
                multi_root_examples.append({
                    "traceID": trace.get("traceID"),
                    "root_count": roots,
                    "total_spans": len(spans),
                })
        elif roots == 0 and len(spans) > 0:
            traces_with_zero_roots += 1

        # Distinct services actually observed in this trace.
        processes = trace.get("processes", {}) or {}
        services_in_trace = {
            proc.get("serviceName") for proc in processes.values() if proc.get("serviceName")
        }
        svc_count = len(services_in_trace)
        service_count_histogram[svc_count] = service_count_histogram.get(svc_count, 0) + 1
        if svc_count > 1:
            traces_spanning_multiple_services += 1
            if len(cross_service_examples) < max_examples:
                cross_service_examples.append({
                    "traceID": trace.get("traceID"),
                    "services": sorted(services_in_trace),
                    "total_spans": len(spans),
                })

    if ijson is not None:
        with open(path, "rb") as f:
            for trace in ijson.items(f, "item"):
                process(trace)
    else:
        data = json.load(open(path))
        for trace in data:
            process(trace)

    def pct(n):
        return round(100 * n / total_traces, 2) if total_traces else 0.0

    return {
        "traces_file": str(path),
        "total_traces": total_traces,
        "total_spans": total_spans,
        "single_span_traces": single_span_traces,
        "single_span_traces_percent": pct(single_span_traces),
        "traces_with_broken_references": traces_with_broken_refs,
        "traces_with_broken_references_percent": pct(traces_with_broken_refs),
        "traces_with_multiple_roots": traces_with_multiple_roots,
        "traces_with_multiple_roots_percent": pct(traces_with_multiple_roots),
        "traces_with_zero_roots": traces_with_zero_roots,
        "total_orphan_spans": total_orphan_spans,
        "traces_spanning_multiple_services": traces_spanning_multiple_services,
        "traces_spanning_multiple_services_percent": pct(traces_spanning_multiple_services),
        "service_count_histogram": service_count_histogram,
        "broken_reference_examples": broken_examples,
        "multiple_root_examples": multi_root_examples,
        "cross_service_examples": cross_service_examples,
    }


def main():
    ap = argparse.ArgumentParser(description="Check context propagation integrity in traces.json")
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    report = analyze(args.traces)
    if args.label:
        report["label"] = args.label

    print(json.dumps(
        {k: v for k, v in report.items() if not k.endswith("examples")},
        indent=2,
    ))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report (with examples) saved to {args.out}")


if __name__ == "__main__":
    main()