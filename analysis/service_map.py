"""
Shared mapping between the short service names used in this analysis
toolkit and the actual OTEL_SERVICE_NAME each service reports to Jaeger.

This copy is set up for the PetClinic MONOLITH (Petclinic-Monolithic
branch). Checked directly against run-with-otel.bat:
    OTEL_SERVICE_NAME=spring-petclinic

IMPORTANT: this file is NOT actually consulted by the pipeline for this
app. compute_coverage.py / reconstruct_journeys.py / etc. only switch into
"microservices mode" (service-aware matching) when static_inventory.json's
route entries carry a "service" field -- and extract_static_inventory_java.py
never adds one for a single --src-root scan, since there's only one
service to begin with. So for the PetClinic monolith, every script stays
in flat/monolith matching mode regardless of what's in this file.

It's kept here (with the single entry below) so the mapping is accurate
if you ever split this app into multiple services later, or reuse this
analysis toolkit copy against a different, genuinely multi-service Java
app (e.g. a Spring Cloud microservices variant of PetClinic) -- in that
case, tag each service's routes during extraction and list every
service's real OTEL_SERVICE_NAME here, same pattern as the Node.js
microservices version:
    {"customer": "customer-service", "products": "product-service", "shopping": "shopping-service"}

If your service names differ, either edit DEFAULT_SERVICE_MAP below, or
pass --service-map path/to/map.json to any script that accepts it.
"""

import json

DEFAULT_SERVICE_MAP = {
    "petclinic": "spring-petclinic",
}


def load_service_map(path=None):
    if path is None:
        return dict(DEFAULT_SERVICE_MAP)
    with open(path) as f:
        return json.load(f)
