#!/usr/bin/env python3
"""
extract_journey_definitions.py
--------------------------------
Parses the k6 workflow scripts (k6/workflows/*.js) into ordered journey
definitions: for each workflow file, the sequence of HTTP calls it makes,
each resolved from the client-facing gateway URL down to the actual
(service, route_template, http_method) that the static inventory records.

Handles:
  - single-line calls:      http.get(`${BASE_URL}/api/vet/vets`)
  - multi-line calls:       http.post(\n  `${BASE_URL}/...`,\n payload,\n params\n)
  - GET/POST/PUT/DELETE
  - step labels pulled from the following check(res, { 'Label': ... }) block
  - path-variable / query-string normalization, and resolution through the
    gateway routing table (service_map.GATEWAY_ROUTES) including the
    StripPrefix behaviour, plus expansion of gateway fan-out calls
    (service_map.GATEWAY_FANOUT) so a single k6 step that hits
    /api/gateway/owners/{id} expands into the full multi-service hop it
    actually produces in a trace.

Usage:
    python extract_journey_definitions.py \
        --workflows-dir /path/to/k6/workflows \
        --out journey_definitions.csv
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from service_map import resolve_gateway_route, otel_name, GATEWAY_FANOUT

HTTP_CALL_RE = re.compile(
    r"http\.(get|post|put|delete|del|patch)\s*\(\s*"
    r"[`'\"]\$\{BASE_URL\}(?P<path>[^`'\"]*)[`'\"]",
    re.IGNORECASE,
)

CHECK_LABEL_RE = re.compile(r"check\s*\(\s*\w+\s*,\s*\{\s*['\"](?P<label>[^'\"]+)['\"]")

METHOD_MAP = {"get": "GET", "post": "POST", "put": "PUT",
              "delete": "DELETE", "del": "DELETE", "patch": "PATCH"}


def _normalize_client_path(raw_path: str) -> str:
    """
    Turn a k6 template-literal path (which may contain ${var} interpolations
    and a query string) into a normalized route for matching, e.g.
    '/api/customer/owners/${ownerId}/pets' -> '/api/customer/owners/{param}/pets'
    """
    path = raw_path.split("?")[0]  # drop query string for route matching
    path = re.sub(r"\$\{[^}]*\}", "{param}", path)
    path = re.sub(r"/\d+(?=/|$)", "/{param}", path)  # literal numeric ids, e.g. /1
    if not path.startswith("/"):
        path = "/" + path
    return path


def parse_workflow_file(filepath: str):
    """Returns an ordered list of step dicts for one workflow file."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    steps = []
    # Walk through the file call-by-call so we can pair each http.X(...) call
    # with the label from its following check(res, {...}) block, and to
    # correctly order steps as they appear (source order == journey order for
    # these workflows, which are simple linear scripts).
    positions = [(m.start(), m) for m in HTTP_CALL_RE.finditer(source)]
    label_positions = [(m.start(), m) for m in CHECK_LABEL_RE.finditer(source)]

    for idx, (pos, m) in enumerate(positions):
        method = METHOD_MAP[m.group(1).lower()]
        raw_path = m.group("path")
        # find the nearest check() label that appears after this call and
        # before the next http.* call (or end of file)
        next_pos = positions[idx + 1][0] if idx + 1 < len(positions) else len(source)
        label = None
        for lp, lm in label_positions:
            if pos < lp < next_pos:
                label = lm.group("label")
                break
        steps.append({
            "step_order": idx + 1,
            "http_method": method,
            "client_path_raw": raw_path,
            "client_path_normalized": _normalize_client_path(raw_path),
            "step_label": label or "",
        })
    return steps


def resolve_step(step):
    """
    Resolve one client-facing step into one-or-more backend
    (service, route, http_method) hops, expanding gateway fan-out where
    applicable. Returns a list of dicts (usually length 1, length 2+ for
    gateway aggregate endpoints).
    """
    client_path = step["client_path_normalized"]
    method = step["http_method"]

    service, backend_path = resolve_gateway_route(client_path)
    if service is None:
        return [{
            "service": "UNRESOLVED", "otel_service_name": "UNRESOLVED",
            "backend_route": client_path, "hop_order": 1, "hop_role": "direct",
        }]

    hops = [{
        "service": service, "otel_service_name": otel_name(service),
        "backend_route": backend_path, "hop_order": 1, "hop_role": "entry",
    }]

    fanout_key = (method, backend_path if service != "api-gateway" else client_path)
    # gateway fan-out is keyed on the gateway-facing path
    fanout_key = (method, client_path)
    for i, (down_service, down_method, down_route) in enumerate(GATEWAY_FANOUT.get(fanout_key, []), start=2):
        hops.append({
            "service": down_service, "otel_service_name": otel_name(down_service),
            "backend_route": down_route, "hop_order": i, "hop_role": "fanout",
        })
    return hops


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workflows-dir", required=True, help="Path to k6/workflows directory.")
    ap.add_argument("--out", default="journey_definitions.csv")
    args = ap.parse_args()

    js_files = sorted(f for f in os.listdir(args.workflows_dir) if f.endswith(".js"))
    if not js_files:
        print(f"No .js workflow files found in {args.workflows_dir}", file=sys.stderr)
        sys.exit(1)

    rows = []
    for fn in js_files:
        journey_name = os.path.splitext(fn)[0]
        filepath = os.path.join(args.workflows_dir, fn)
        steps = parse_workflow_file(filepath)
        if not steps:
            print(f"  [WARN] no http.* calls found in {fn}")
            continue
        for step in steps:
            hops = resolve_step(step)
            for hop in hops:
                rows.append({
                    "journey": journey_name,
                    "step_order": step["step_order"],
                    "step_label": step["step_label"],
                    "client_http_method": step["http_method"],
                    "client_path": step["client_path_normalized"],
                    "hop_order": hop["hop_order"],
                    "hop_role": hop["hop_role"],
                    "service": hop["service"],
                    "otel_service_name": hop["otel_service_name"],
                    "backend_route": hop["backend_route"],
                })
        print(f"{journey_name}: {len(steps)} client steps -> {sum(len(resolve_step(s)) for s in steps)} service hops")

    fieldnames = ["journey", "step_order", "step_label", "client_http_method", "client_path",
                  "hop_order", "hop_role", "service", "otel_service_name", "backend_route"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    unresolved = [r for r in rows if r["service"] == "UNRESOLVED"]
    if unresolved:
        print(f"\n[WARN] {len(unresolved)} step(s) could not be resolved to a backend service "
              f"(no matching gateway route). Check service_map.GATEWAY_ROUTES.")
    print(f"\nWrote {len(rows)} journey-hop rows across {len(js_files)} journeys -> {args.out}")


if __name__ == "__main__":
    main()
