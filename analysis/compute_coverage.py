#!/usr/bin/env python3
"""
compute_coverage.py
---------------------
Compares the static operational inventory (extract_static_inventory_java.py's
static_inventory.csv output) against a collected traces.json to answer:
what fraction of the endpoints the code CAN serve actually show up as
root-cause spans in the collected traces, at this sampling ratio?

This is the CSV/trace_utils-based version of this script -- it matches the
API that aggregate_coverage_by_sampling.py and run_quality_analysis.py
import: load_inventory() and build_observed_index().

Usage (standalone):
    python compute_coverage.py \
        --inventory static_inventory.csv \
        --traces datasets/traces/microservices/sample100/browseOwners/run1/traces.json \
        --out coverage_report.csv
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_utils import load_traces, normalize_route


def load_inventory(path):
    """
    Reads static_inventory.csv (extract_static_inventory_java.py's output)
    into a list of dict rows: service, otel_service_name, http_method,
    route_template, route_template_normalized, class_name, method_name,
    source_file, line_number.
    """
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_observed_index(traces_path):
    """
    Streams every span across every trace in traces_path and builds:
        observed[(service, HTTP_METHOD, route_normalized)] = occurrence count
    matching every span that carries a resolvable service + http_method +
    route (not just root spans -- ANY span with HTTP semantic-convention
    tags counts as an observed endpoint call).

    Returns (observed, n_traces, n_spans, span_service_names) where
    span_service_names is the set of distinct Jaeger serviceNames actually
    seen (handy for a quick "did tracing even reach this service?" sanity
    check independent of route matching).
    """
    observed = {}
    n_traces = 0
    n_spans = 0
    span_service_names = set()

    for trace in load_traces(traces_path):
        n_traces += 1
        for s in trace["spans"]:
            n_spans += 1
            if s["service"]:
                span_service_names.add(s["service"])
            if not (s["service"] and s["http_method"] and s["route_raw"]):
                continue
            key = (s["service"], s["http_method"].upper(), normalize_route(s["route_raw"]))
            observed[key] = observed.get(key, 0) + 1

    return observed, n_traces, n_spans, span_service_names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory", required=True, help="static_inventory.csv")
    ap.add_argument("--traces", required=True)
    ap.add_argument("--out", default="coverage_report.csv")
    args = ap.parse_args()

    inventory = load_inventory(args.inventory)
    observed, n_traces, n_spans, span_service_names = build_observed_index(args.traces)

    rows = []
    covered = 0
    for entry in inventory:
        key = (entry["service"], entry["http_method"].upper(), entry["route_template_normalized"])
        count = observed.get(key, 0)
        if count > 0:
            covered += 1
        rows.append({
            "service": entry["service"],
            "http_method": entry["http_method"],
            "route_template": entry["route_template"],
            "route_template_normalized": entry["route_template_normalized"],
            "class_name": entry["class_name"],
            "method_name": entry["method_name"],
            "observed_span_count": count,
            "covered": count > 0,
        })

    total = len(inventory)
    coverage_pct = (covered / total * 100) if total else 0.0

    fieldnames = ["service", "http_method", "route_template", "route_template_normalized",
                  "class_name", "method_name", "observed_span_count", "covered"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Analyzed {n_traces} traces / {n_spans} spans from {args.traces}")
    print(f"Services actually seen in traces: {sorted(span_service_names)}")
    print(f"Endpoint coverage: {covered}/{total} ({coverage_pct:.1f}%)")

    uncovered = [r for r in rows if not r["covered"]]
    if uncovered:
        print(f"\nUncovered endpoints ({len(uncovered)}):")
        for r in uncovered:
            print(f"  [{r['service']}] {r['http_method']} {r['route_template']}")

    print(f"\nWrote per-endpoint coverage detail -> {args.out}")


if __name__ == "__main__":
    main()