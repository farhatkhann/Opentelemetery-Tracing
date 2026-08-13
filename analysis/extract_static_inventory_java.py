"""
Extracts a static "operational inventory" from a Spring Boot Java monolith's
source code -- every REST/MVC route (@GetMapping/@PostMapping/etc., with
class-level @RequestMapping prefixes correctly merged in) and every custom
repository method (interfaces extending Repository/CrudRepository/
JpaRepository/PagingAndSortingRepository), plus any @Service-annotated
class methods if present.

This plays the same role JavaParser plays in the study this toolkit is
based on, but uses javalang (a pure-Python Java parser) instead of the
actual JavaParser JVM library -- functionally equivalent for this purpose
(parsing annotations, class/interface/method declarations), and avoids
needing a JVM + Maven dependency resolution in the analysis environment.
If you specifically need JavaParser itself, this script's extraction logic
translates directly (same annotation-walking approach), you'd just be
running it from a small Java/Maven project instead of `pip install`.

Usage:
    python extract_static_inventory_java.py --src-root ../src/main/java --out static_inventory.json

KNOWN LIMITATIONS (read before trusting the coverage % this feeds into):
  - Repository layer only captures methods TEXTUALLY DECLARED in the
    interface (e.g. findByLastName). Inherited CRUD methods from
    JpaRepository/CrudRepository (save, findById, findAll, deleteById,
    etc.) are NOT included, since they don't appear in the source file at
    all -- there's nothing for a static analyzer to find. If your app
    calls those inherited methods directly, they simply won't show up in
    this inventory; that's a real blind spot of static source analysis,
    not a bug to fix here.
  - Bare `@RequestMapping` with no `method = RequestMethod.X` attribute
    applies to ALL HTTP methods in Spring. This script emits it once as
    "ANY /path" rather than expanding to every verb -- match against
    traces accordingly (an "ANY" entry should be considered matched if
    ANY method+path combination for that path appears in your traces).
  - Path variables stay in their Spring form (e.g. "/owners/{ownerId}"),
    which is what Spring's own HTTP server instrumentation typically
    reports as the span name too -- so this should match real traces
    directly without the manual ":id"-style fixups the Node.js version
    sometimes needed.
"""

import argparse
import json
import re
from pathlib import Path

import javalang

HTTP_MAPPING_ANNOTATIONS = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}

REPOSITORY_BASE_TYPES = {"Repository", "CrudRepository", "JpaRepository", "PagingAndSortingRepository"}


def annotation_element_to_paths(element):
    """
    Normalizes an annotation's `element` (whatever shape javalang gave us)
    down to a list of literal path strings. Returns [] if no path-like
    value was found (e.g. a bare @RequestMapping with only `method=...`).
    """
    if element is None:
        return []

    if isinstance(element, javalang.tree.Literal):
        return [element.value.strip('"')]

    if isinstance(element, javalang.tree.ElementArrayValue):
        return [v.value.strip('"') for v in element.values if isinstance(v, javalang.tree.Literal)]

    if isinstance(element, list):  # list of ElementValuePair, e.g. @RequestMapping(value=..., method=...)
        for pair in element:
            if getattr(pair, "name", None) in ("value", "path"):
                return annotation_element_to_paths(pair.value)

    return []


def annotation_http_method(annotation):
    """
    Returns the HTTP verb for a mapping annotation, or "ANY" for a bare
    @RequestMapping with no explicit method attribute.
    """
    if annotation.name in HTTP_MAPPING_ANNOTATIONS:
        return HTTP_MAPPING_ANNOTATIONS[annotation.name]

    if annotation.name == "RequestMapping":
        element = annotation.element
        if isinstance(element, list):
            for pair in element:
                if getattr(pair, "name", None) == "method":
                    member = getattr(pair.value, "member", None)
                    if member:
                        return member.upper()
        return "ANY"

    return None


def join_paths(prefix: str, suffix: str) -> str:
    prefix = prefix or ""
    suffix = suffix or ""
    combined = prefix.rstrip("/") + "/" + suffix.lstrip("/")
    if not combined.startswith("/"):
        combined = "/" + combined
    combined = re.sub(r"/+", "/", combined)
    if len(combined) > 1 and combined.endswith("/"):
        combined = combined[:-1]
    return combined


def class_has_annotation(node, name):
    return any(a.name == name for a in getattr(node, "annotations", []) or [])


def class_level_prefixes(node):
    for ann in getattr(node, "annotations", []) or []:
        if ann.name == "RequestMapping":
            paths = annotation_element_to_paths(ann.element)
            if paths:
                return paths
    return [""]


def extends_repository(node):
    """True if an interface's extends clause references a Spring Data repository base type."""
    extends = getattr(node, "extends", None)
    if not extends:
        return False
    if not isinstance(extends, list):
        extends = [extends]
    for e in extends:
        name = getattr(e, "name", None)
        if name in REPOSITORY_BASE_TYPES:
            return True
    return False


def extract_routes_from_class(node, rel_path, controller_name):
    routes = []
    prefixes = class_level_prefixes(node)

    for method in getattr(node, "methods", []) or []:
        for ann in method.annotations:
            if ann.name not in HTTP_MAPPING_ANNOTATIONS and ann.name != "RequestMapping":
                continue
            http_method = annotation_http_method(ann)
            suffixes = annotation_element_to_paths(ann.element) or [""]

            for prefix in prefixes:
                for suffix in suffixes:
                    full_path = join_paths(prefix, suffix)
                    routes.append({
                        "name": f"{http_method} {full_path}",
                        "layer": "route",
                        "class": controller_name,
                        "method": method.name,
                        "file": rel_path,
                        "line": method.position.line if method.position else None,
                    })
    return routes


def extract_repository_methods(node, rel_path, interface_name):
    methods = []
    for method in getattr(node, "methods", []) or []:
        methods.append({
            "name": method.name,
            "class": interface_name,
            "layer": "repository",
            "file": rel_path,
            "line": method.position.line if method.position else None,
        })
    return methods


def extract_service_methods(node, rel_path, class_name):
    methods = []
    for method in getattr(node, "methods", []) or []:
        if method.name == "<init>":
            continue
        methods.append({
            "name": method.name,
            "class": class_name,
            "layer": "service",
            "file": rel_path,
            "line": method.position.line if method.position else None,
        })
    return methods


def process_file(java_file: Path, src_root: Path):
    routes, services, repos = [], [], []
    rel_path = str(java_file.relative_to(src_root))

    try:
        source = java_file.read_text(encoding="utf-8", errors="replace")
        tree = javalang.parse.parse(source)
    except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError) as e:
        print(f"  ! failed to parse {rel_path}: {e}")
        return routes, services, repos

    for path, node in tree.filter(javalang.tree.ClassDeclaration):
        if class_has_annotation(node, "Controller") or class_has_annotation(node, "RestController"):
            routes.extend(extract_routes_from_class(node, rel_path, node.name))
        elif class_has_annotation(node, "Service"):
            services.extend(extract_service_methods(node, rel_path, node.name))

    for path, node in tree.filter(javalang.tree.InterfaceDeclaration):
        if extends_repository(node):
            repos.extend(extract_repository_methods(node, rel_path, node.name))

    return routes, services, repos


def main():
    ap = argparse.ArgumentParser(description="Extract static operational inventory from a Spring Boot Java monolith")
    ap.add_argument("--src-root", required=True, help="Path to src/main/java")
    ap.add_argument("--out", default="static_inventory.json", help="Output JSON path")
    args = ap.parse_args()

    src_root = Path(args.src_root).resolve()

    all_routes, all_services, all_repos = [], [], []

    java_files = sorted(src_root.rglob("*.java"))
    print(f"Scanning {len(java_files)} .java files under {src_root}\n")

    for java_file in java_files:
        routes, services, repos = process_file(java_file, src_root)
        if routes or services or repos:
            print(f"  {java_file.relative_to(src_root)}: "
                  f"{len(routes)} routes, {len(services)} service methods, {len(repos)} repository methods")
        all_routes.extend(routes)
        all_services.extend(services)
        all_repos.extend(repos)

    all_operations = all_routes + all_services + all_repos

    inventory = {
        "total_operations": len(all_operations),
        "by_layer": {
            "route": len(all_routes),
            "service": len(all_services),
            "repository": len(all_repos),
        },
        "operations": all_operations,
    }

    with open(args.out, "w") as f:
        json.dump(inventory, f, indent=2)

    print("\n" + "=" * 60)
    print("Static Inventory Extraction Complete")
    print("=" * 60)
    print(f"Routes             : {len(all_routes)}")
    print(f"Service methods    : {len(all_services)}")
    print(f"Repository methods : {len(all_repos)}")
    print(f"Total operations   : {len(all_operations)}")
    if len(all_services) == 0:
        print("\nNOTE: 0 @Service-annotated classes found. If this app follows the "
              "classic Spring PetClinic pattern (controllers call repositories "
              "directly, no service layer), that's expected -- not a script bug.")
    print(f"\nSaved to: {args.out}")


if __name__ == "__main__":
    main()
