"""
trace_utils.py
---------------
Shared helpers for reading a Jaeger JSON trace export and normalizing each
span down to (service, http_method, route_template) plus the identifiers
needed for context-propagation and journey-reconstruction analysis.

Supports both the standard Jaeger UI/API export shape:
    {"data": [ {"traceID": ..., "spans": [ {...} ], "processes": {...}} ]}
and a flat list of trace objects (some export tools drop the outer "data").

Each span is expected to carry, in its tags (Jaeger classic) or attributes
(OTLP-ish exports), standard HTTP semantic-convention keys:
    http.method / http.request.method
    http.route (best) OR http.target / url.path / http.url (fallback,
        requires path-template normalization since these carry real IDs)
    http.status_code
Span-to-service comes from span.process.serviceName (classic Jaeger, via a
per-trace processID -> process lookup) or span.serviceName directly.
"""
import json
import re


def load_traces(path: str):
    """Yields one dict per trace, each with a normalized 'spans' list."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    traces = raw.get("data", raw) if isinstance(raw, dict) else raw
    if not isinstance(traces, list):
        raise ValueError(f"Unrecognized trace file shape in {path}")

    for trace in traces:
        yield normalize_trace(trace)


def _tags_to_dict(tag_list):
    d = {}
    for t in tag_list or []:
        key = t.get("key")
        if key is None:
            continue
        d[key] = t.get("value")
    return d


def normalize_trace(trace: dict):
    """
    Returns {'trace_id':..., 'spans': [normalized_span, ...]}
    normalized_span = {
        span_id, parent_span_id, operation_name, service, http_method,
        route_raw, start_time_us, duration_us, status_code, tags
    }
    """
    trace_id = trace.get("traceID") or trace.get("trace_id") or trace.get("traceId")
    processes = trace.get("processes", {}) or {}

    # Build parent map from Jaeger's 'references' (CHILD_OF) since spans
    # don't carry an explicit parent field by default.
    spans_raw = trace.get("spans", [])
    norm_spans = []
    for s in spans_raw:
        span_id = s.get("spanID") or s.get("span_id") or s.get("spanId")
        tags = _tags_to_dict(s.get("tags")) if "tags" in s else (s.get("attributes") or {})

        # service name resolution
        service = None
        proc_id = s.get("processID") or s.get("process_id")
        if proc_id and proc_id in processes:
            service = processes[proc_id].get("serviceName")
        if not service:
            proc = s.get("process") or {}
            service = proc.get("serviceName") or s.get("serviceName")

        parent_span_id = None
        refs = s.get("references", [])
        for ref in refs:
            if ref.get("refType", "CHILD_OF") == "CHILD_OF":
                parent_span_id = ref.get("spanID") or ref.get("span_id")
                break
        if parent_span_id is None and s.get("parentSpanID"):
            parent_span_id = s.get("parentSpanID")

        http_method = tags.get("http.method") or tags.get("http.request.method")
        route_raw = (tags.get("http.route") or tags.get("http.target")
                     or tags.get("url.path") or tags.get("http.url"))
        status_code = tags.get("http.status_code") or tags.get("http.response.status_code")

        norm_spans.append({
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "operation_name": s.get("operationName") or s.get("name"),
            "service": service,
            "http_method": http_method,
            "route_raw": route_raw,
            "start_time_us": s.get("startTime") or s.get("startTimeUnixNano"),
            "duration_us": s.get("duration"),
            "status_code": status_code,
            "tags": tags,
        })
    return {"trace_id": trace_id, "spans": norm_spans}


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_NUMERIC_RE = re.compile(r"(?<=/)\d+(?=/|$)")


def normalize_route(raw_path: str) -> str:
    """
    Best-effort normalization of a raw request path/URL into the same
    {param}-style template used by the static inventory, so traces can be
    matched against it even when http.route wasn't captured and we only
    have the literal http.target/http.url.
    """
    if not raw_path:
        return None
    path = raw_path
    # strip scheme+host if a full URL was captured
    path = re.sub(r"^https?://[^/]+", "", path)
    path = path.split("?")[0]
    if not path.startswith("/"):
        path = "/" + path
    path = _UUID_RE.sub("{param}", path)
    path = _NUMERIC_RE.sub("{param}", path)
    path = re.sub(r"\{[^}]+\}", "{param}", path)  # collapse any named {xxx} placeholder too
    while "//" in path:
        path = path.replace("//", "/")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path
