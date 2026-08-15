#!/usr/bin/env python3
"""
extract_static_inventory_java.py
---------------------------------
Static inventory extractor for the Petclinic-Microservices Java codebase.

For each service, walks the Java source tree, parses every .java file with
`javalang`, and records every Spring MVC / WebFlux REST endpoint it finds:
  - class-level @RequestMapping prefix (string or array-valued, merged in)
  - method-level @GetMapping/@PostMapping/@PutMapping/@DeleteMapping/
    @PatchMapping/@RequestMapping(method=...)
  - path variables normalized to {param}, and bare '*' wildcards normalized
    to {param} as well, so route templates match cleanly against real trace
    URLs later.

Multi-service usage (mirrors the Node microservices extractor):
    python extract_static_inventory_java.py \
        --service customers-service=/path/to/spring-petclinic-customers-service/src/main/java \
        --service vets-service=/path/to/spring-petclinic-vets-service/src/main/java \
        --service visits-service=/path/to/spring-petclinic-visits-service/src/main/java \
        --service api-gateway=/path/to/spring-petclinic-api-gateway/src/main/java \
        --out static_inventory.csv

If --service is omitted entirely, falls back to service_map.DEFAULT_SERVICE_PATHS
resolved relative to --repo-root (or the current directory).

Output columns:
    service, otel_service_name, http_method, route_template, class_name,
    method_name, source_file, line_number
"""
import argparse
import csv
import os
import re
import sys

import javalang

# javalang (targets older Java grammar) chokes on modern syntax that this
# codebase uses in DTOs/config: Java 17 text blocks ("""..."""). Records are
# left alone (routers/controllers are never declared as records here), but
# text blocks appear inside a couple of real @RestController classes
# (e.g. genai-service's PetclinicChatClient, which has a real @PostMapping
# alongside a """...""" system-prompt string), so silently failing to parse
# those files would drop real endpoints. Neutralize text blocks before
# parsing, preserving line count so reported line numbers stay accurate.
_TEXT_BLOCK_RE = re.compile(r'"""(.*?)"""', re.DOTALL)


def _strip_text_blocks(source: str) -> str:
    def _replace(match):
        newline_count = match.group(0).count("\n")
        return '"TEXT_BLOCK_PLACEHOLDER"' + ("\n" * newline_count)
    return _TEXT_BLOCK_RE.sub(_replace, source)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from service_map import DEFAULT_SERVICE_PATHS, otel_name

MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

CONTROLLER_ANNOTATIONS = {"RestController", "Controller"}


def _annotation_value_strings(annotation):
    """
    Pull out all string literal values from an annotation, whether it's
    written as @Foo("x"), @Foo(value = "x"), or @Foo({"x", "y"}).
    Returns a list (possibly empty) of raw string values (quotes stripped).
    """
    values = []
    if annotation.element is None:
        return values

    def collect(el):
        if isinstance(el, javalang.tree.Literal):
            v = el.value
            if isinstance(v, str) and v.startswith('"') and v.endswith('"'):
                values.append(v[1:-1])
        elif isinstance(el, javalang.tree.ElementArrayValue):
            for sub in el.values:
                collect(sub)
        elif isinstance(el, javalang.tree.ElementValuePair):
            # only care about value=/path= pairs, ignore method=/produces=/etc.
            if el.name in ("value", "path"):
                collect(el.value)

    element = annotation.element
    if isinstance(element, list):
        for e in element:
            collect(e)
    else:
        collect(element)
    return values


def _annotation_method_override(annotation):
    """For @RequestMapping(method = RequestMethod.GET) style, extract GET/POST/etc."""
    element = annotation.element
    if element is None:
        return None
    items = element if isinstance(element, list) else [element]
    for el in items:
        if isinstance(el, javalang.tree.ElementValuePair) and el.name == "method":
            val = el.value
            # value may be MemberReference (RequestMethod.GET) or an array of those
            candidates = val.values if isinstance(val, javalang.tree.ElementArrayValue) else [val]
            for c in candidates:
                member = getattr(c, "member", None)
                if member:
                    return member.upper()
    return None


def _normalize_path(path: str) -> str:
    if not path:
        path = ""
    if not path.startswith("/"):
        path = "/" + path
    # collapse Spring's Ant-style single-segment wildcard '*' into a named param
    segments = path.split("/")
    norm = []
    for seg in segments:
        if seg == "*":
            norm.append("{param}")
        elif seg.startswith("{") and seg.endswith("}"):
            norm.append(seg)
        else:
            norm.append(seg)
    result = "/".join(norm)
    # collapse duplicate slashes and trailing slash (except root)
    while "//" in result:
        result = result.replace("//", "/")
    if len(result) > 1 and result.endswith("/"):
        result = result[:-1]
    return result


def _normalize_for_matching(route_template: str) -> str:
    """
    Collapse any named path variable ({ownerId}, {petId}, ...) down to the
    generic {param} placeholder used by trace_utils.normalize_route() and
    extract_journey_definitions.py, so all three pipelines key on the same
    shape regardless of what the Java code happened to name its variables.
    """
    return re.sub(r"\{[^}]+\}", "{param}", route_template)


def _join_paths(prefix: str, sub: str) -> str:
    prefix = prefix.rstrip("/")
    if not sub or sub == "/":
        return _normalize_path(prefix or "/")
    sub = sub if sub.startswith("/") else "/" + sub
    return _normalize_path(prefix + sub)


def extract_from_file(filepath: str):
    """Yields dicts: http_method, route_template, class_name, method_name, line."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    source = _strip_text_blocks(source)

    try:
        tree = javalang.parse.parse(source)
    except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError) as e:
        # Still a real failure (e.g. Java records, which this codebase uses
        # only for DTOs, never for @RestController classes). Warn but don't
        # abort the whole scan.
        print(f"  [WARN] could not parse {filepath}: {e}", file=sys.stderr)
        return

    for _, class_decl in tree.filter(javalang.tree.ClassDeclaration):
        class_annotations = class_decl.annotations or []
        ann_names = {a.name for a in class_annotations}
        if not (ann_names & CONTROLLER_ANNOTATIONS):
            continue

        # class-level @RequestMapping prefix(es) - array-valued means the
        # class is reachable under multiple prefixes; emit endpoints under each.
        class_prefixes = [""]
        for ann in class_annotations:
            if ann.name == "RequestMapping":
                vals = _annotation_value_strings(ann)
                if vals:
                    class_prefixes = vals

        for method in class_decl.methods:
            method_annotations = method.annotations or []
            for ann in method_annotations:
                http_method = None
                sub_paths = [""]

                if ann.name in MAPPING_ANNOTATIONS:
                    http_method = MAPPING_ANNOTATIONS[ann.name]
                    vals = _annotation_value_strings(ann)
                    if vals:
                        sub_paths = vals
                elif ann.name == "RequestMapping":
                    http_method = _annotation_method_override(ann) or "GET"
                    vals = _annotation_value_strings(ann)
                    if vals:
                        sub_paths = vals
                else:
                    continue

                for class_prefix in class_prefixes:
                    for sub_path in sub_paths:
                        route = _join_paths(class_prefix, sub_path)
                        yield {
                            "http_method": http_method,
                            "route_template": route,
                            "route_template_normalized": _normalize_for_matching(route),
                            "class_name": class_decl.name,
                            "method_name": method.name,
                            "line": getattr(method.position, "line", None),
                        }


def scan_service(service_name: str, src_root: str):
    rows = []
    if not os.path.isdir(src_root):
        print(f"  [WARN] source path not found for {service_name}: {src_root}", file=sys.stderr)
        return rows

    java_files = []
    for dirpath, _, filenames in os.walk(src_root):
        for fn in filenames:
            if fn.endswith(".java"):
                java_files.append(os.path.join(dirpath, fn))

    for fp in sorted(java_files):
        for entry in extract_from_file(fp):
            rows.append({
                "service": service_name,
                "otel_service_name": otel_name(service_name),
                "http_method": entry["http_method"],
                "route_template": entry["route_template"],
                "route_template_normalized": entry["route_template_normalized"],
                "class_name": entry["class_name"],
                "method_name": entry["method_name"],
                "source_file": os.path.relpath(fp, src_root),
                "line_number": entry["line"],
            })
    return rows


def parse_service_args(service_args):
    """--service NAME=PATH  ->  {NAME: PATH}"""
    mapping = {}
    for item in service_args or []:
        if "=" not in item:
            raise ValueError(f"--service must be NAME=PATH, got: {item}")
        name, path = item.split("=", 1)
        mapping[name.strip()] = path.strip()
    return mapping


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--service", action="append",
                     help="NAME=PATH to source root, repeatable. If omitted, uses DEFAULT_SERVICE_PATHS.")
    ap.add_argument("--repo-root", default=".",
                     help="Repo root to resolve DEFAULT_SERVICE_PATHS against (only used if --service is omitted).")
    ap.add_argument("--out", default="static_inventory.csv", help="Output CSV path.")
    args = ap.parse_args()

    services = parse_service_args(args.service)
    if not services:
        services = {name: os.path.join(args.repo_root, rel)
                    for name, rel in DEFAULT_SERVICE_PATHS.items()}

    all_rows = []
    for name, path in services.items():
        print(f"Scanning {name}: {path}")
        rows = scan_service(name, path)
        print(f"  -> {len(rows)} endpoints found")
        all_rows.extend(rows)

    fieldnames = ["service", "otel_service_name", "http_method", "route_template",
                  "route_template_normalized", "class_name", "method_name",
                  "source_file", "line_number"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(all_rows, key=lambda r: (r["service"], r["route_template"], r["http_method"])):
            writer.writerow(row)

    print(f"\nWrote {len(all_rows)} total endpoints across {len(services)} services -> {args.out}")


if __name__ == "__main__":
    main()
