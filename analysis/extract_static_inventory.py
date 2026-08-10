"""
Extracts a static "operational inventory" from Node/Express source code
using Tree-sitter -- i.e. every route and every service/repository method
that could plausibly produce a traced operation.

This is the ground truth used later to measure trace coverage: what
fraction of operations that the code CAN perform actually show up as
spans in the collected traces.

Supports TWO modes:

1) Single source tree (monolith):
    python extract_static_inventory.py --src-root ../src --out static_inventory.json

2) Multiple services (microservices) -- repeat --service NAME=PATH for
   each one. Every extracted operation is tagged with "service": NAME so
   downstream analysis can match against per-service Jaeger data (each
   microservice reports to Jaeger under its own OTEL_SERVICE_NAME):
    python extract_static_inventory.py \
        --service customer=../customer/src \
        --service products=../products/src \
        --service shopping=../shopping/src \
        --out static_inventory.json

Do NOT pass a --service for the gateway -- it's a thin express-http-proxy
with no business-logic routes/services/repositories of its own, so there's
nothing for this script to extract there.

Expects, per source root (adjust --api-dir/--service-dir/--repo-dir if
your layout differs):
    {src-root}/api/*.js                        -- Express route files
    {src-root}/services/*.js                   -- service layer
    {src-root}/database/repository/*.js        -- repository layer

*.test.js files are always skipped.
"""

import argparse
import json
from pathlib import Path

import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser

JS_LANGUAGE = Language(tsjavascript.language())
parser = Parser(JS_LANGUAGE)

# Express methods we recognize as route definitions: app.get(...), app.put(...), etc.
HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}


def read_source(path: Path) -> bytes:
    return path.read_bytes()


def node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def extract_routes(tree, source: bytes, file_path: str, service: str = None):
    routes = []

    def visit(node):
        if node.type == "call_expression":
            callee = node.child_by_field_name("function")
            if callee is not None and callee.type == "member_expression":
                obj = callee.child_by_field_name("object")
                prop = callee.child_by_field_name("property")
                if (
                    obj is not None and prop is not None
                    and node_text(obj, source) in ("app", "router")
                    and node_text(prop, source) in HTTP_METHODS
                ):
                    method = node_text(prop, source).upper()
                    args = node.child_by_field_name("arguments")
                    route_path = None
                    if args is not None:
                        for child in args.named_children:
                            if child.type == "string":
                                route_path = node_text(child, source).strip("'\"")
                                break
                    if route_path is not None:
                        entry = {
                            "name": f"{method} {route_path}",
                            "layer": "route",
                            "file": file_path,
                            "line": node.start_point[0] + 1,
                        }
                        if service is not None:
                            entry["service"] = service
                        routes.append(entry)
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return routes


def extract_class_methods(tree, source: bytes, file_path: str, layer: str, service: str = None):
    methods = []

    def visit(node, class_name=None):
        current_class = class_name

        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                current_class = node_text(name_node, source)

        if node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                method_name = node_text(name_node, source)
                if method_name != "constructor":
                    entry = {
                        "name": method_name,
                        "class": current_class,
                        "layer": layer,
                        "file": file_path,
                        "line": node.start_point[0] + 1,
                    }
                    if service is not None:
                        entry["service"] = service
                    methods.append(entry)

        for child in node.children:
            visit(child, current_class)

    visit(tree.root_node)
    return methods


def process_directory(dir_path: Path, layer: str, src_root: Path, service: str = None):
    results = []
    if not dir_path.exists():
        print(f"    (skipped, not found: {dir_path})")
        return results

    for js_file in sorted(dir_path.glob("*.js")):
        if js_file.name.endswith(".test.js"):
            continue

        source = read_source(js_file)
        tree = parser.parse(source)
        rel_path = str(js_file.relative_to(src_root))

        if layer == "route":
            entries = extract_routes(tree, source, rel_path, service)
        else:
            entries = extract_class_methods(tree, source, rel_path, layer, service)

        results.extend(entries)
        print(f"    {js_file.name}: {len(entries)} operations")

    return results


def extract_from_src_root(src_root: Path, api_dir: str, service_dir: str, repo_dir: str, service: str = None):
    label = f" [{service}]" if service else ""

    print(f"  Routes{label}")
    routes = process_directory(src_root / api_dir, "route", src_root, service)

    print(f"  Service methods{label}")
    services_ = process_directory(src_root / service_dir, "service", src_root, service)

    print(f"  Repository methods{label}")
    repositories = process_directory(src_root / repo_dir, "repository", src_root, service)

    return routes, services_, repositories


def parse_service_arg(value: str):
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"--service must be NAME=PATH, got: {value!r}")
    name, path = value.split("=", 1)
    return name.strip(), path.strip()


def main():
    ap = argparse.ArgumentParser(description="Extract static operational inventory")
    ap.add_argument("--src-root", default=None, help="Path to a single src/ directory (monolith mode)")
    ap.add_argument("--service", action="append", default=[], type=parse_service_arg,
                     help="NAME=PATH to a service's src/ directory. Repeat for each microservice.")
    ap.add_argument("--api-dir", default="api", help="Relative path to route files")
    ap.add_argument("--service-dir", default="services", help="Relative path to service files")
    ap.add_argument("--repo-dir", default="database/repository", help="Relative path to repository files")
    ap.add_argument("--out", default="static_inventory.json", help="Output JSON path")
    args = ap.parse_args()

    if not args.src_root and not args.service:
        ap.error("Provide either --src-root (monolith) or one or more --service NAME=PATH (microservices)")
    if args.src_root and args.service:
        ap.error("Use either --src-root OR --service, not both")

    all_routes, all_services, all_repositories = [], [], []
    by_service = {}

    if args.src_root:
        print("=" * 60)
        print("Extracting static inventory (single source tree)")
        print("=" * 60)
        src_root = Path(args.src_root).resolve()
        routes, services_, repositories = extract_from_src_root(
            src_root, args.api_dir, args.service_dir, args.repo_dir
        )
        all_routes += routes
        all_services += services_
        all_repositories += repositories
    else:
        print("=" * 60)
        print("Extracting static inventory (microservices)")
        print("=" * 60)
        for service_name, service_path in args.service:
            print(f"\n--- Service: {service_name} ({service_path}) ---")
            src_root = Path(service_path).resolve()
            routes, services_, repositories = extract_from_src_root(
                src_root, args.api_dir, args.service_dir, args.repo_dir, service=service_name
            )
            all_routes += routes
            all_services += services_
            all_repositories += repositories
            by_service[service_name] = {
                "route": len(routes),
                "service": len(services_),
                "repository": len(repositories),
                "total": len(routes) + len(services_) + len(repositories),
            }

    all_operations = all_routes + all_services + all_repositories

    inventory = {
        "total_operations": len(all_operations),
        "by_layer": {
            "route": len(all_routes),
            "service": len(all_services),
            "repository": len(all_repositories),
        },
        "operations": all_operations,
    }
    if by_service:
        inventory["by_service"] = by_service

    with open(args.out, "w") as f:
        json.dump(inventory, f, indent=2)

    print("\n" + "=" * 60)
    print("Static Inventory Extraction Complete")
    print("=" * 60)
    print(f"Routes             : {len(all_routes)}")
    print(f"Service methods    : {len(all_services)}")
    print(f"Repository methods : {len(all_repositories)}")
    print(f"Total operations   : {len(all_operations)}")
    if by_service:
        print("\nBy service:")
        for svc, counts in by_service.items():
            print(f"  {svc}: {counts['total']} "
                  f"(route={counts['route']}, service={counts['service']}, repository={counts['repository']})")
    print(f"\nSaved to: {args.out}")


if __name__ == "__main__":
    main()