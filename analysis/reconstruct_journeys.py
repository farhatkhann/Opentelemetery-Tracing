#!/usr/bin/env python3
"""
reconstruct_journeys.py
--------------------------
Attempts to reconstruct each k6-defined user journey (extract_journey_definitions.py
output) from the raw trace data, and measures how much of the journey survives
under sampling.

Because each client-side journey step in this app is its OWN top-level HTTP
request (the k6 workflows are not themselves traced as one parent - each
http.get/post call gets its own trace, except for the gateway fan-out route,
which is a single trace containing multiple service hops - see
check_context_propagation.py), "reconstructing a journey" here means:

  For a given journey (e.g. "browseOwners" = GET /owners -> GET /owners/{id}
  -> GET /vets), find traces whose ROOT span matches each journey step's
  (service, method, route) in order, and group them by temporal proximity
  (same k6 iteration => calls happen within a short window, since the
  workflow scripts issue them back-to-back with a single sleep(1) at the end).

This produces:
  - a per-journey reconstruction rate: fraction of journeys where ALL steps
    were found together within the time window vs. only some steps
    (partial reconstruction - the effect of trace sampling dropping
    individual requests) vs. none.
  - for the gateway fan-out journey pattern, reconstruction additionally
    requires the full fan-out (checked via check_context_propagation logic)
    within the single trace.

Usage:
    python reconstruct_journeys.py \
        --traces traces.json \
        --journeys journey_definitions.csv \
        --window-seconds 5 \
        --out journey_reconstruction_report.csv
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trace_utils import load_traces, normalize_route


def load_journey_defs(path):
    journeys = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["hop_role"] != "entry":
                continue  # only the entry hop identifies a distinct client-triggered root span
            journeys[row["journey"]].append({
                "step_order": int(row["step_order"]),
                "service": row["service"],
                "http_method": row["client_http_method"],
                "route": row["backend_route"],
            })
    for name in journeys:
        journeys[name].sort(key=lambda s: s["step_order"])
    return journeys


def index_root_spans(traces_path):
    """
    Returns list of root-span records:
    {trace_id, service, http_method, route, start_time_us}
    Root span = a span with no parent (the entry point of that trace).
    """
    roots = []
    for trace in load_traces(traces_path):
        for s in trace["spans"]:
            if s["parent_span_id"]:
                continue
            if not (s["service"] and s["http_method"] and s["route_raw"]):
                continue
            roots.append({
                "trace_id": trace["trace_id"],
                "service": s["service"],
                "http_method": s["http_method"].upper(),
                "route": normalize_route(s["route_raw"]),
                "start_time_us": s["start_time_us"] or 0,
            })
    roots.sort(key=lambda r: r["start_time_us"])
    return roots


def reconstruct(journey_steps, roots, window_seconds):
    """
    Greedy reconstruction: slide a window over time-sorted root spans; for
    each candidate starting root matching journey_steps[0], look ahead within
    window_seconds for the remaining steps in order (each step matched at
    most once, earliest qualifying candidate consumed). Returns a list of
    reconstruction attempts, each: {'steps_found': n, 'steps_total': N,
    'complete': bool, 'trace_ids': [...]}.
    """
    window_us = window_seconds * 1_000_000
    n = len(journey_steps)
    used = [False] * len(roots)
    attempts = []

    for i, r in enumerate(roots):
        if used[i]:
            continue
        step0 = journey_steps[0]
        if not (r["service"] == step0["service"] and r["http_method"] == step0["http_method"]
                and r["route"] == step0["route"]):
            continue

        found_idx = [i]
        cursor_time = r["start_time_us"]
        for step in journey_steps[1:]:
            match_j = None
            for j in range(i + 1, len(roots)):
                if used[j] or j in found_idx:
                    continue
                cand = roots[j]
                if cand["start_time_us"] - cursor_time > window_us:
                    break  # roots are time-sorted; no point scanning further
                if (cand["service"] == step["service"] and cand["http_method"] == step["http_method"]
                        and cand["route"] == step["route"]):
                    match_j = j
                    break
            if match_j is not None:
                found_idx.append(match_j)
                cursor_time = roots[match_j]["start_time_us"]

        for idx in found_idx:
            used[idx] = True

        attempts.append({
            "steps_found": len(found_idx),
            "steps_total": n,
            "complete": len(found_idx) == n,
            "trace_ids": [roots[k]["trace_id"] for k in found_idx],
        })

    return attempts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--traces", required=True)
    ap.add_argument("--journeys", required=True, help="journey_definitions.csv")
    ap.add_argument("--window-seconds", type=float, default=5.0,
                     help="Max time gap allowed between consecutive journey steps to count as the same user iteration.")
    ap.add_argument("--out", default="journey_reconstruction_report.csv")
    args = ap.parse_args()

    journeys = load_journey_defs(args.journeys)
    roots = index_root_spans(args.traces)
    print(f"Indexed {len(roots)} root spans from {args.traces}")

    rows = []
    for name, steps in journeys.items():
        if not steps:
            continue
        attempts = reconstruct(steps, roots, args.window_seconds)
        n_attempts = len(attempts)
        n_complete = sum(1 for a in attempts if a["complete"])
        avg_frac = (sum(a["steps_found"] / a["steps_total"] for a in attempts) / n_attempts) if n_attempts else 0.0
        rows.append({
            "journey": name,
            "steps_in_definition": len(steps),
            "reconstruction_attempts": n_attempts,
            "fully_reconstructed": n_complete,
            "partially_reconstructed": n_attempts - n_complete,
            "full_reconstruction_rate": f"{(n_complete / n_attempts * 100):.1f}%" if n_attempts else "n/a",
            "avg_step_completeness": f"{avg_frac * 100:.1f}%" if n_attempts else "n/a",
        })
        print(f"{name}: {n_attempts} candidate iterations found, "
              f"{n_complete} fully reconstructed ({(n_complete/n_attempts*100) if n_attempts else 0:.1f}%)")

    fieldnames = ["journey", "steps_in_definition", "reconstruction_attempts",
                  "fully_reconstructed", "partially_reconstructed",
                  "full_reconstruction_rate", "avg_step_completeness"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote per-journey reconstruction summary -> {args.out}")


if __name__ == "__main__":
    main()
