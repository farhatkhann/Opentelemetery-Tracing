#!/usr/bin/env python3
"""
check_context_propagation.py
------------------------------
Checks whether distributed-tracing context (trace ID + parent/child span
links) is being propagated correctly across the three cross-service call
patterns this application actually has:

  1. Gateway fan-out: api-gateway's GET /api/gateway/owners/{id} calls
     customers-service AND visits-service internally (service_map.GATEWAY_FANOUT).
     A correctly-instrumented request should produce ONE trace containing all
     three spans, with the two downstream spans' parent chain resolving back
     to the api-gateway root span.
  2. Orphaned spans: any span in a trace whose parent_span_id is set but does
     not correspond to another span present in the same trace (context was
     received but the parent span is missing - usually a sampling artifact
     or an instrumentation gap, not a propagation failure per se, but worth
     surfacing separately).
  3. Broken fan-out: traces that contain the api-gateway root span for a
     known fan-out route but are MISSING one or both expected downstream
     spans entirely - this is the actual propagation-loss signal on the
     server side when the caller doesn't forward its trace headers.

Usage:
    python check_context_propagation.py --traces traces.json --out context_propagation_report.csv
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_utils import load_traces, normalize_route
from service_map import GATEWAY_FANOUT

# Build lookup: (root_service, root_method, root_route_normalized) -> [(down_service, down_method, down_route), ...]
FANOUT_BY_ROOT_ROUTE = {}
for (method, gateway_client_path), downstream in GATEWAY_FANOUT.items():
    # the root span's own route is the backend route on api-gateway itself
    # (== the gateway_client_path here since strip_segments == 0 for /api/gateway/**)
    FANOUT_BY_ROOT_ROUTE[("api-gateway", method, normalize_route(gateway_client_path))] = downstream


def analyze_trace(trace):
    spans = trace["spans"]
    span_by_id = {s["span_id"]: s for s in spans if s["span_id"]}

    findings = []

    # --- orphaned spans -----------------------------------------------
    for s in spans:
        if s["parent_span_id"] and s["parent_span_id"] not in span_by_id:
            findings.append({
                "issue": "orphaned_span",
                "service": s["service"],
                "route": normalize_route(s["route_raw"]) if s["route_raw"] else s["operation_name"],
                "detail": f"parent_span_id={s['parent_span_id']} not present in this trace",
            })

    # --- fan-out completeness ------------------------------------------
    root_spans = [s for s in spans if not s["parent_span_id"]]
    for root in root_spans:
        if not root["service"] or not root["http_method"] or not root["route_raw"]:
            continue
        key = (root["service"], root["http_method"].upper(), normalize_route(root["route_raw"]))
        expected = FANOUT_BY_ROOT_ROUTE.get(key)
        if not expected:
            continue
        # descendants of this root (any depth), matched by (service, route)
        descendant_ids = set()
        frontier = [root["span_id"]]
        while frontier:
            nxt = []
            for s in spans:
                if s["parent_span_id"] in frontier and s["span_id"] not in descendant_ids:
                    descendant_ids.add(s["span_id"])
                    nxt.append(s["span_id"])
            frontier = nxt
        descendants = [span_by_id[i] for i in descendant_ids]

        for down_service, down_method, down_route in expected:
            down_route_norm = normalize_route(down_route)
            matched = any(
                d["service"] == down_service
                and (d["http_method"] or "").upper() == down_method
                and normalize_route(d["route_raw"]) == down_route_norm
                for d in descendants
            )
            if not matched:
                findings.append({
                    "issue": "broken_fanout",
                    "service": root["service"],
                    "route": key[2],
                    "detail": f"expected child span {down_method} {down_route} on {down_service} not found in trace",
                })

    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default="context_propagation_report.csv")
    args = ap.parse_args()

    rows = []
    n_traces = 0
    n_fanout_roots = 0
    for trace in load_traces(args.traces):
        n_traces += 1
        findings = analyze_trace(trace)
        for f in findings:
            rows.append({"trace_id": trace["trace_id"], **f})
        # count how many fan-out-eligible roots this trace had, for a denominator
        for s in trace["spans"]:
            if not s["parent_span_id"] and s["service"] and s["http_method"] and s["route_raw"]:
                key = (s["service"], s["http_method"].upper(), normalize_route(s["route_raw"]))
                if key in FANOUT_BY_ROOT_ROUTE:
                    n_fanout_roots += 1

    fieldnames = ["trace_id", "issue", "service", "route", "detail"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    orphaned = [r for r in rows if r["issue"] == "orphaned_span"]
    broken = [r for r in rows if r["issue"] == "broken_fanout"]

    print(f"Analyzed {n_traces} traces.")
    print(f"Fan-out-eligible root spans found: {n_fanout_roots}")
    if n_fanout_roots:
        pct_broken = len(broken) / (n_fanout_roots * 2) * 100  # 2 expected downstream calls per known fan-out route
        print(f"Broken fan-out hops: {len(broken)} "
              f"(~{pct_broken:.1f}% of expected downstream hops missing)")
    print(f"Orphaned spans (parent referenced but missing from trace): {len(orphaned)}")
    print(f"\nWrote detailed findings -> {args.out}")


if __name__ == "__main__":
    main()
