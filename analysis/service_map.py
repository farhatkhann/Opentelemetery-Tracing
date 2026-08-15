"""
service_map.py
---------------
Central registry of everything the other scripts need to know about how the
Petclinic-Microservices application maps to real Jaeger/OTEL service names,
how the API gateway routes external traffic to backend services, and which
backend services the gateway calls directly (fan-out) for its own aggregate
endpoints.

This is the single place to edit if the deployment topology changes (e.g. a
service gets renamed, or a new gateway route is added).
"""

# ---------------------------------------------------------------------------
# 1) Real OTEL service names, taken verbatim from each service's
#    src/main/resources/application.yml -> spring.application.name
# ---------------------------------------------------------------------------
OTEL_SERVICE_NAMES = {
    "api-gateway": "api-gateway",
    "customers-service": "customers-service",
    "vets-service": "vets-service",
    "visits-service": "visits-service",
    "genai-service": "genai-service",
    "admin-server": "admin-server",
    "discovery-server": "discovery-server",
    "config-server": "config-server",
}

# Services that actually expose business REST endpoints worth inventorying
# for coverage analysis. The infra services (discovery/config/admin) are
# excluded by default since they aren't targets of the k6 journeys.
APPLICATION_SERVICES = [
    "api-gateway",
    "customers-service",
    "vets-service",
    "visits-service",
    "genai-service",
]

# ---------------------------------------------------------------------------
# 2) Spring Cloud Gateway routing table (from api-gateway application.yml).
#    Each route strips the given number of leading path segments before
#    forwarding to the backend service. This is how a client-facing k6 call
#    like GET /api/customer/owners/1 becomes GET /owners/1 on the
#    customers-service, which is what the static inventory records.
#
#    prefix       -> (target_service, strip_segments)
# ---------------------------------------------------------------------------
GATEWAY_ROUTES = {
    "/api/vet":      ("vets-service", 2),
    "/api/visit":    ("visits-service", 2),
    "/api/customer": ("customers-service", 2),
    "/api/genai":    ("genai-service", 2),
    # /api/gateway/** is NOT proxied - it's handled by the gateway's own
    # ApiGatewayController, which internally fans out to other services.
    "/api/gateway":  ("api-gateway", 0),
}

# ---------------------------------------------------------------------------
# 3) Gateway-internal fan-out calls: endpoints on api-gateway's own
#    ApiGatewayController that, in turn, issue their own HTTP calls to other
#    backend services (via WebClient, load-balanced by service name, NOT
#    through the external gateway routes above). These matter for
#    context-propagation and journey-reconstruction: a single client request
#    to /api/gateway/owners/{id} should produce a trace spanning THREE
#    services (api-gateway -> customers-service, api-gateway -> visits-service).
#
#    gateway_route -> list of (downstream_service, downstream_route, http_method)
# ---------------------------------------------------------------------------
GATEWAY_FANOUT = {
    ("GET", "/api/gateway/owners/{ownerId}"): [
        ("customers-service", "GET", "/owners/{ownerId}"),
        ("visits-service", "GET", "/pets/visits"),
    ],
}

# ---------------------------------------------------------------------------
# 4) Local checkout paths, relative to the repo root, used by
#    extract_static_inventory_java.py's default --service arguments.
# ---------------------------------------------------------------------------
DEFAULT_SERVICE_PATHS = {
    "api-gateway": "spring-petclinic-api-gateway/src/main/java",
    "customers-service": "spring-petclinic-customers-service/src/main/java",
    "vets-service": "spring-petclinic-vets-service/src/main/java",
    "visits-service": "spring-petclinic-visits-service/src/main/java",
    "genai-service": "spring-petclinic-genai-service/src/main/java",
}


def resolve_gateway_route(path: str):
    """
    Given an external, client-facing path (e.g. '/api/customer/owners/1'),
    return (target_service, backend_path) after applying StripPrefix, or
    (None, None) if no gateway route matches.
    """
    for prefix, (service, strip_n) in GATEWAY_ROUTES.items():
        if path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?"):
            if strip_n == 0:
                return service, path
            segments = path.split("?")[0].strip("/").split("/")
            remainder = segments[strip_n:]
            backend_path = "/" + "/".join(remainder) if remainder else "/"
            return service, backend_path
    return None, None


def otel_name(short_name: str) -> str:
    return OTEL_SERVICE_NAMES.get(short_name, short_name)
