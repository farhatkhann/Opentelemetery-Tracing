"""
Shared mapping between the short service names used in this analysis
toolkit (matching --service NAME in extract_static_inventory.py and the
SERVICES keys in k6/utils/config.js: "customer", "products", "shopping")
and the actual OTEL_SERVICE_NAME each service reports to Jaeger as
(checked directly against each service's .env.dev):
    customer  -> customer-service
    products  -> product-service   (singular "product", not "products")
    shopping  -> shopping-service

If your service names differ or you add more services, either edit
DEFAULT_SERVICE_MAP below, or pass --service-map path/to/map.json to any
script that accepts it, with contents like:
    {"customer": "customer-service", "products": "product-service", "shopping": "shopping-service"}
"""

import json

DEFAULT_SERVICE_MAP = {
    "customer": "customer-service",
    "products": "product-service",
    "shopping": "shopping-service",
}


def load_service_map(path=None):
    if path is None:
        return dict(DEFAULT_SERVICE_MAP)
    with open(path) as f:
        return json.load(f)
