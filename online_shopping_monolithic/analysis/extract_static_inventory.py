"""
Extracts a static "operational inventory" from the Node/Express monolith's
source code using Tree-sitter -- i.e. every route and every service/
repository method that could plausibly produce a traced operation.

This is the ground truth used later to measure trace coverage: what
fraction of operations that the code CAN perform actually show up as
spans in the collected traces.

Usage:
    python extract_static_inventory.py --src-root ../src --out static_inventory.json

Expects (adjust --api-dir/--service-dir/--repo-dir if your layout differs):
    {src-root}/api/*.js                        -- Express route files
    {src-root}/services/*.js                   -- service layer
    {src-root}/database/repository/*.js        -- repository layer
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


def extract_routes(tree, source: bytes, file_path: str):
    """
    Finds Express route definitions of the form:
        app.get('/path', ...handlers)
        app.put("/path", middleware, async (req, res, next) => {...})
    Returns entries like: { "name": "GET /path", "layer": "route", ... }
    """
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
                        routes.append({
                            "name": f"{method} {route_path}",
                            "layer": "route",
                            "file": file_path,
                            "line": node.start_point[0] + 1,
                        })
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return routes


def extract_class_methods(tree, source: bytes, file_path: str, layer: str):
    """
    Finds method definitions inside classes:
        class CustomerService {
            async AddToWishlist(...) { ... }
        }
    Returns entries like: { "name": "AddToWishlist", "layer": "service", ... }
    Skips the constructor.
    """
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
                    methods.append({
                        "name": method_name,
                        "class": current_class,
                        "layer": layer,
                        "file": file_path,
                        "line": node.start_point[0] + 1,
                    })

        for child in node.children:
            visit(child, current_class)

    visit(tree.root_node)
    return methods


def process_directory(dir_path: Path, extractor_fn, layer: str, src_root: Path):
    results = []
    if not dir_path.exists():
        print(f"  (skipped, not found: {dir_path})")
        return results

    for js_file in sorted(dir_path.glob("*.js")):
        source = read_source(js_file)
        tree = parser.parse(source)
        rel_path = str(js_file.relative_to(src_root))

        if layer == "route":
            entries = extract_routes(tree, source, rel_path)
        else:
            entries = extract_class_methods(tree, source, rel_path, layer)

        results.extend(entries)
        print(f"  {js_file.name}: {len(entries)} operations")

    return results


def main():
    ap = argparse.ArgumentParser(description="Extract static operational inventory")
    ap.add_argument("--src-root", required=True, help="Path to the src/ directory")
    ap.add_argument("--api-dir", default="api", help="Relative path to route files")
    ap.add_argument("--service-dir", default="services", help="Relative path to service files")
    ap.add_argument("--repo-dir", default="database/repository", help="Relative path to repository files")
    ap.add_argument("--out", default="static_inventory.json", help="Output JSON path")
    args = ap.parse_args()

    src_root = Path(args.src_root).resolve()

    print("=" * 60)
    print("Extracting Routes")
    print("=" * 60)
    routes = process_directory(src_root / args.api_dir, extract_routes, "route", src_root)

    print("\n" + "=" * 60)
    print("Extracting Service Methods")
    print("=" * 60)
    services = process_directory(src_root / args.service_dir, extract_class_methods, "service", src_root)

    print("\n" + "=" * 60)
    print("Extracting Repository Methods")
    print("=" * 60)
    repositories = process_directory(src_root / args.repo_dir, extract_class_methods, "repository", src_root)

    all_operations = routes + services + repositories

    inventory = {
        "total_operations": len(all_operations),
        "by_layer": {
            "route": len(routes),
            "service": len(services),
            "repository": len(repositories),
        },
        "operations": all_operations,
    }

    with open(args.out, "w") as f:
        json.dump(inventory, f, indent=2)

    print("\n" + "=" * 60)
    print("Static Inventory Extraction Complete")
    print("=" * 60)
    print(f"Routes             : {len(routes)}")
    print(f"Service methods    : {len(services)}")
    print(f"Repository methods : {len(repositories)}")
    print(f"Total operations   : {len(all_operations)}")
    print(f"\nSaved to: {args.out}")


if __name__ == "__main__":
    main()