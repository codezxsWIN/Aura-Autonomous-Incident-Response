from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from run_demo_scenario import print_stage, request_json, wait_for_api


def build_telemetry() -> list[dict[str, Any]]:
    base = datetime.now(timezone.utc)
    common: dict[str, Any] = {
        "user_id": "usr_john_chen",
        "tenant_id": "tenant_northstar",
        "session_id": "sess_checkout_vip_7f3a",
        "user_tier": "Enterprise",
        "cart_value": 50_000,
    }
    events: list[dict[str, Any]] = []

    def add(offset_ms: int, **values: Any) -> None:
        events.append(
            {
                **common,
                "event_id": f"evt_{uuid4().hex}",
                "timestamp": (base + timedelta(milliseconds=offset_ms)).isoformat(),
                **values,
            }
        )

    for index, (mouse_x, mouse_y) in enumerate(
        [(210, 360), (480, 210), (235, 390), (520, 195), (255, 410)]
    ):
        add(index * 55, event_type="mouse_move", mouse_x=mouse_x, mouse_y=mouse_y)
    for index in range(4):
        add(
            310 + index * 115,
            event_type="click",
            click_target="#complete-purchase",
        )
    for index, latency_ms in enumerate((212, 4_870, 5_000)):
        add(
            800 + index * 120,
            event_type="api_request",
            service="checkout-service" if index == 0 else "redis-checkout",
            latency_ms=latency_ms,
            http_status=200 if index == 0 else 504,
        )
    for index in range(3):
        add(
            1_180 + index * 45,
            event_type="dom_mutation",
            metadata={"region": "checkout-summary", "unexpected": True},
        )
    add(
        1_350,
        event_type="anomaly",
        service="redis-checkout",
        latency_ms=5_000,
        http_status=504,
        metadata={"baseline_ms": 200, "cpu_percent": 96},
    )
    return events


def wait_for_terminal_state(
    base_url: str, incident_id: str, timeout_seconds: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        state = request_json(f"{base_url}/api/state")
        if state.get("incident_id") == incident_id and state.get("status") in {
            "resolved",
            "escalated",
        }:
            return state
        time.sleep(0.02)
    raise RuntimeError(f"Incident {incident_id} did not reach a terminal state")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prove a live checkout failure triggers Aura, changes the observed "
            "data plane, and succeeds on retry."
        )
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    try:
        health = wait_for_api(base_url, args.timeout)
        request_json(f"{base_url}/api/demo/reset", method="POST", payload={})
        request_json(
            f"{base_url}/api/live-checkout/fault",
            method="POST",
            payload={"tenant_id": "tenant_northstar", "enabled": True},
        )
        started = time.perf_counter()
        checkout_payload = {
            "user_id": "usr_john_chen",
            "tenant_id": "tenant_northstar",
            "session_id": "sess_checkout_vip_7f3a",
            "cart_value": 50_000,
        }
        try:
            before = request_json(
                f"{base_url}/api/live-checkout/attempt",
                method="POST",
                payload=checkout_payload,
            )
            before_status = 200
        except urllib.error.HTTPError as exc:
            if exc.code != 503:
                raise
            before_status = exc.code
            before = json.load(exc)
        decisions = []
        round_trip_times_ms = []
        for event in build_telemetry():
            accepted_at = time.perf_counter()
            decisions.append(
                request_json(
                    f"{base_url}/api/telemetry",
                    method="POST",
                    payload=event,
                )
            )
            round_trip_times_ms.append(
                (time.perf_counter() - accepted_at) * 1_000
            )
        triggers = [decision for decision in decisions if decision["incident_triggered"]]
        if len(triggers) != 1:
            raise AssertionError(f"Expected one incident claim, observed {len(triggers)}")
        incident_id = triggers[0]["incident_id"]
        state = wait_for_terminal_state(base_url, incident_id, args.timeout)
        after = request_json(
            f"{base_url}/api/live-checkout/attempt",
            method="POST",
            payload=checkout_payload,
        )
        live_state = request_json(f"{base_url}/api/live-checkout/state")
        presentation_ms = (time.perf_counter() - started) * 1_000
        sorted_acceptance = sorted(
            float(decision["acceptance_ms"]) for decision in decisions
        )
        sorted_round_trip = sorted(round_trip_times_ms)
        p95_rank = 0.95 * (len(sorted_acceptance) - 1)
        lower_index = math.floor(p95_rank)
        upper_index = math.ceil(p95_rank)
        interpolation = p95_rank - lower_index
        acceptance_p95_ms = (
            sorted_acceptance[lower_index] * (1 - interpolation)
            + sorted_acceptance[upper_index] * interpolation
        )
        round_trip_p95_ms = (
            sorted_round_trip[lower_index] * (1 - interpolation)
            + sorted_round_trip[upper_index] * interpolation
        )
    except (
        AssertionError,
        KeyError,
        RuntimeError,
        urllib.error.HTTPError,
        urllib.error.URLError,
    ) as exc:
        print(f"Telemetry scenario failed: {exc}", file=sys.stderr)
        return 1

    final_decision = decisions[-1]
    action = state["remediation_actions"][-1]
    mutation = action.get("mutation") or {}
    probe = state.get("verification", {}).get("details", {}).get("probe") or {}
    healthy = all(node["status"] == "healthy" for node in state["graph"])
    invariants = {
        "live failure observed": before_status == 503
        and before.get("http_status") == 503
        and before.get("fault_active") is True,
        "sixteen events retained": final_decision["session_window_size"] == 16,
        "single incident identity": final_decision["incident_id"] == incident_id,
        "resolved": state["status"] == "resolved",
        "root cause": state["root_cause_node"] == "redis-checkout",
        "safe action succeeded": action["safety_level"] == "SAFE"
        and action["status"] == "succeeded",
        "live data changed": mutation.get("previous_fault_enabled") is True
        and mutation.get("fault_enabled") is False
        and mutation.get("changed") is True
        and mutation.get("source") == "live-local-action",
        "verification healthy": state["verification"]["status"] == "healthy",
        "independent live probe": probe.get("http_status") == 200
        and probe.get("fault_active") is False
        and probe.get("source") == "live-local-http-verification"
        and probe.get("request_path") == "/api/live-checkout/attempt",
        "next checkout succeeds": after.get("http_status") == 200
        and after.get("outcome") == "completed"
        and after.get("fault_active") is False,
        "live state matches action": live_state.get("fault_enabled") is False
        and (live_state.get("last_mutation") or {}).get("mutation_id")
        == mutation.get("mutation_id"),
        "graph healthy": healthy,
        "telemetry p95 under 25 ms": acceptance_p95_ms < 25,
        "automation under 800 ms": state["elapsed_ms"] < 800,
    }
    failed = [name for name, passed in invariants.items() if not passed]
    if failed:
        print(
            f"Telemetry scenario invariant failure: {', '.join(failed)}; "
            f"ingress p95={acceptance_p95_ms:.2f} ms, "
            f"automation={state['elapsed_ms']:.2f} ms, "
            f"wall clock={presentation_ms:.2f} ms",
            file=sys.stderr,
        )
        return 2

    print_stage("before", "HTTP 503 / fault_enabled=true")
    print_stage("activation", f"16 ordinary events -> {incident_id}")
    print_stage("trigger", f"window size {triggers[0]['session_window_size']}")
    print_stage("root cause", " -> ".join(state["graph_path"]))
    print_stage("policy", f"{action['tool']} [{action['safety_level']}]")
    print_stage(
        "mutation",
        f"{mutation['mutation_id']} / fault_enabled true -> false",
    )
    print_stage(
        "verification",
        f"HTTP {probe['http_status']} / {probe['source']}",
    )
    print_stage("retry", "HTTP 200 / checkout completed")
    print_stage("ingress p95", f"{acceptance_p95_ms:.2f} ms")
    print_stage("roundtrip p95", f"{round_trip_p95_ms:.2f} ms")
    print_stage("automation", f"{state['elapsed_ms']:.2f} ms")
    print_stage("wall clock", f"{presentation_ms:.2f} ms")
    print_stage("outcome", state["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())