from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from typing import Any


def request_json(
    url: str, *, method: str = "GET", payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Aura-Demo-Key": os.getenv("AURA_LOCAL_DEMO_KEY", "aura-local-demo"),
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def wait_for_api(base_url: str, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return request_json(f"{base_url}/api/health")
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Aura API was not ready within {timeout_seconds}s: {last_error}")


def print_stage(label: str, value: str) -> None:
    print(f"[{label:<13}] {value}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the $50k Aura VIP checkout recovery scenario."
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--open", action="store_true", help="Open the dashboard first.")
    parser.add_argument("--no-reset", action="store_true")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    try:
        health = wait_for_api(base_url, args.timeout)
        print_stage(
            "runtime",
            f"{health['services']['supervisor']} / {health['services']['graph']} / "
            f"{health['services']['event_bus']}",
        )
        if args.open:
            webbrowser.open(base_url)
            print_stage("dashboard", base_url)
        if not args.no_reset:
            request_json(f"{base_url}/api/demo/reset", method="POST", payload={})
        print_stage("inject", "checkout-service latency 200ms -> 5000ms")
        result = request_json(
            f"{base_url}/api/demo/run",
            method="POST",
            payload={
                "user_id": "usr_john_chen",
                "tenant_id": "tenant_northstar",
                "user_tier": "Enterprise",
                "cart_value": 50_000,
                "inject_service": "redis-checkout",
            },
        )
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1

    traces = result.get("traces", [])
    for trace in traces:
        print_stage(trace["agent"], trace["summary"])
    action = result["remediation_actions"][-1]
    ticket = result.get("ticket") or {}
    print_stage("root cause", " -> ".join(result["graph_path"]))
    print_stage("blast radius", f"3 Enterprise users / $120,000 MRR at risk")
    print_stage("tool call", f"{action['tool']} [{action['safety_level']}] -> {action['status']}")
    print_stage("user push", result["user_message"])
    print_stage("incident", f"{ticket.get('key')} / {ticket.get('severity')}")
    print_stage("outcome", f"{result['status']} in {result['elapsed_ms']:.2f}ms")

    healthy = all(node["status"] == "healthy" for node in result["graph"])
    recovery_probes = [
        event
        for event in result["telemetry"]
        if event.get("metadata", {}).get("recovery_probe")
    ]
    mutation = action.get("mutation") or {}
    probe = result.get("verification", {}).get("details", {}).get("probe") or {}
    invariants = {
        "resolved": result["status"] == "resolved",
        "healthy graph": healthy,
        "safe action succeeded": action["safety_level"] == "SAFE"
        and action["status"] == "succeeded",
        "live action recorded": mutation.get("source") == "live-local-action"
        and mutation.get("fault_enabled") is False,
        "verification healthy": result["verification"]["status"] == "healthy",
        "checkout probe observed": probe.get("http_status") == 200
        and probe.get("fault_active") is False
        and probe.get("source") == "live-local-http-verification"
        and probe.get("request_path") == "/api/live-checkout/attempt",
        "one recovery observation": len(recovery_probes) == 1,
        "policy recorded": bool(result["policy_decisions"]),
        "automation under 800 ms": result["elapsed_ms"] < 800,
    }
    failed = [name for name, passed in invariants.items() if not passed]
    if failed:
        print(
            f"Demo invariant failure: {', '.join(failed)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())