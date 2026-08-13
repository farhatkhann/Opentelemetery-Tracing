"""
Extracts the expected ordered sequence of HTTP calls ("journey steps") from
each k6 workflow script, so we have a ground-truth journey definition to
compare reconstructed traces against.

This is a light regex-based extractor. It recognizes TWO call shapes:

  Monolith style (single BASE_URL, no service field emitted):
    http.get(`${BASE_URL}/some/path`, ...)
    http.put(`${BASE_URL}/cart`, ...)

  Microservices style (a SERVICES map keyed by short service name, e.g.
  SERVICES = { customer: ..., products: ..., shopping: ... } in
  k6/utils/config.js -- each step is tagged with which service it targets):
    http.get(`${SERVICES.products}/`, ...)
    http.put(`${SERVICES.shopping}/cart`, ...)

Calls are extracted in file order (k6 default functions run top-to-bottom
per iteration, so file order == step order).

Usage:
    python extract_journey_definitions.py --k6-dir ../k6/workflows --out journeys.json

Output (journeys.json):
  Monolith style:
    "checkout_workflow": [
        {"step": 1, "operation": "GET /"},
        {"step": 2, "operation": "PUT /cart"},
        ...
    ]
  Microservices style (note the added "service" key per step):
    "checkout_workflow": [
        {"step": 1, "service": "products", "operation": "GET /"},
        {"step": 2, "service": "shopping", "operation": "PUT /cart"},
        ...
    ]

IMPORTANT: This is a heuristic. Review journeys.json manually after running --
in particular:
  - Calls built from concatenated/templated path segments (e.g. a product ID
    interpolated into the path) will be extracted with the template literal
    intact (e.g. "GET /${productId}"), which will NOT match a real trace's
    operationName (e.g. "GET /507f1f77..."). Edit these by hand to match how
    the route is declared (e.g. "GET /:id" if that's what appears in your
    traces / static_inventory.json), or drop the step if your app doesn't
    collapse path params in span names.
  - Calls hidden inside helper functions (e.g. k6/utils/multipleAuth.js's
    getToken()) won't be picked up from the workflow file itself. Check
    k6/utils/*.js separately if a workflow uses shared helpers that make
    their own HTTP calls (e.g. a login call inside getToken()).
"""

import argparse
import json
import re
from pathlib import Path

# Matches: http.<method>(`...${BASE_URL}<path>` , ...            (monolith)
# or:      http.<method>(`...${SERVICES.<name>}<path>` , ...     (microservices)
# or:      http.<method>(`<path>`, ...                            (no variable, rare)
CALL_RE = re.compile(
    r"http\.(get|put|post|patch|delete|del|head|options)\s*\(\s*`"
    r"(?:\$\{(?:BASE_URL|SERVICES\.(\w+))\})?"
    r"([^`]*)`",
    re.IGNORECASE,
)

METHOD_MAP = {
    "get": "GET", "put": "PUT", "post": "POST", "patch": "PATCH",
    "delete": "DELETE", "del": "DELETE", "head": "HEAD", "options": "OPTIONS",
}


def extract_steps(js_path: Path):
    """
    Returns a list of (service_or_None, "METHOD /path") tuples, in file order.
    service is None for monolith-style BASE_URL calls or bare-string calls.
    """
    text = js_path.read_text(encoding="utf-8", errors="replace")
    steps = []
    for match in CALL_RE.finditer(text):
        method = METHOD_MAP.get(match.group(1).lower(), match.group(1).upper())
        service = match.group(2)  # None unless SERVICES.<name> was used
        path = match.group(3).strip()
        path = path.split("?", 1)[0]  # drop query string -- not part of the route pattern
        if not path.startswith("/"):
            path = "/" + path
        steps.append((service, f"{method} {path}"))
    return steps


def main():
    ap = argparse.ArgumentParser(description="Extract journey definitions from k6 workflow scripts")
    ap.add_argument("--k6-dir", required=True, help="Path to k6/workflows directory")
    ap.add_argument("--out", default="journeys.json", help="Output JSON path")
    args = ap.parse_args()

    k6_dir = Path(args.k6_dir)
    journeys = {}

    for js_file in sorted(k6_dir.glob("*.js")):
        steps = extract_steps(js_file)
        workflow_name = js_file.stem

        step_entries = []
        for i, (service, op) in enumerate(steps):
            entry = {"step": i + 1, "operation": op}
            if service:
                entry["service"] = service
            step_entries.append(entry)
        journeys[workflow_name] = step_entries

        preview = [f"[{s}] {op}" if s else op for s, op in steps]
        print(f"{js_file.name}: {len(steps)} steps -> {preview}")

    with open(args.out, "w") as f:
        json.dump(journeys, f, indent=2)

    print(f"\nSaved {len(journeys)} journey definitions to {args.out}")
    print("Review the output file by hand before trusting it for analysis -- see the docstring at the top of this script.")


if __name__ == "__main__":
    main()
