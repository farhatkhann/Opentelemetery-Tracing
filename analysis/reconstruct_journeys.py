"""
Checks how much of an expected user journey (from journeys.json, produced
by extract_journey_definitions.py) survives in a collected traces.json.

IMPORTANT SCOPE NOTE: k6 issues each step of a workflow as a separate HTTP
request, and this app does not propagate a single trace context across
those separate requests (there's no shared traceparent header carried
between them in the k6 scripts). So each step lands in its OWN Jaeger
trace, not as spans within one big "journey trace". This script therefore
measures journey completeness at the RUN level: for one full k6 run of a
workflow (e.g. datasets/traces/monolith/sample10/checkout_workflow/run1/),
what fraction of the workflow's expected steps appear as AT LEAST ONE span
somewhere in that run's traces.json?

This is the honest question sampling can actually degrade here: as sampling
drops, some step-request traces get dropped entirely by the head-based
sampler, so rarer/lower-volume steps in a workflow can disappear from the
collected data first. If you want per-iteration (per-VU-loop) journey
reconstruction instead of per-run, you'd need to add explicit trace-context
propagation or correlation IDs across the k6 requests in a single iteration
first -- that's a bigger change to the app/k6 scripts, not something this
script can back into after the fact.

Usage:
    python reconstruct_journeys.py \
        --journeys journeys.json \
        --traces ../datasets/traces/monolith/sample10/checkout_workflow/run1/traces.json \
        --workflow checkout_workflow \
        --out journey_sample10_checkout_run1.json
"""

import argparse
import json

try:
    import ijson
except ImportError:
    ijson = None

import service_map as service_map_mod


def stream_operation_set(path):
    """
    Returns (ops, service_op_pairs, trace_count).
    ops:              flat set of operationName, any service (monolith use).
    service_op_pairs: set of (jaeger_service_name, operationName) tuples
                       (microservices use), built from each span's
                       processID -> trace["processes"][processID]["serviceName"].
    """
    ops = set()
    service_op_pairs = set()
    trace_count = 0

    def process(trace):
        nonlocal trace_count
        trace_count += 1
        processes = trace.get("processes", {}) or {}
        for sp in trace.get("spans", []):
            name = sp.get("operationName")
            if not name:
                continue
            ops.add(name)
            proc_id = sp.get("processID")
            svc_name = processes.get(proc_id, {}).get("serviceName") if proc_id else None
            if svc_name:
                service_op_pairs.add((svc_name, name))

    if ijson is not None:
        with open(path, "rb") as f:
            for trace in ijson.items(f, "item"):
                process(trace)
    else:
        data = json.load(open(path))
        for trace in data:
            process(trace)

    return ops, service_op_pairs, trace_count


def main():
    ap = argparse.ArgumentParser(description="Check journey reconstruction completeness under sampling")
    ap.add_argument("--journeys", required=True, help="journeys.json from extract_journey_definitions.py")
    ap.add_argument("--traces", required=True, help="traces.json for one run of one workflow")
    ap.add_argument("--workflow", required=True, help="Workflow key in journeys.json, e.g. checkout_workflow")
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default=None)
    ap.add_argument("--service-map", default=None,
                     help="JSON file mapping journey 'service' names to Jaeger serviceName "
                          "(default: built-in customer/products/shopping mapping). "
                          "Only used when journey steps carry a 'service' field.")
    args = ap.parse_args()

    journeys = json.load(open(args.journeys))
    if args.workflow not in journeys:
        raise SystemExit(
            f"Workflow '{args.workflow}' not found in {args.journeys}. "
            f"Available: {list(journeys.keys())}"
        )

    steps = journeys[args.workflow]
    is_microservices = any("service" in s for s in steps)
    observed_ops, observed_service_pairs, trace_count = stream_operation_set(args.traces)

    if is_microservices:
        svc_map = service_map_mod.load_service_map(args.service_map)
        expected_steps = []
        present = []
        missing = []
        for s in steps:
            jaeger_service = svc_map.get(s.get("service"))
            display = f"[{s.get('service')}] {s['operation']}"
            expected_steps.append(display)
            if jaeger_service and (jaeger_service, s["operation"]) in observed_service_pairs:
                present.append(display)
            else:
                missing.append(display)
    else:
        expected_steps = [step["operation"] for step in steps]
        present = [s for s in expected_steps if s in observed_ops]
        missing = [s for s in expected_steps if s not in observed_ops]

    completeness_pct = round(100 * len(present) / len(expected_steps), 2) if expected_steps else 0.0

    report = {
        "label": args.label,
        "workflow": args.workflow,
        "traces_file": str(args.traces),
        "microservices_mode": is_microservices,
        "trace_count_in_run": trace_count,
        "expected_step_count": len(expected_steps),
        "steps_present": present,
        "steps_missing": missing,
        "journey_completeness_percent": completeness_pct,
        "fully_reconstructable": len(missing) == 0,
    }

    print(json.dumps(report, indent=2))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
