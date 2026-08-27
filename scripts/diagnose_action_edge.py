#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

ACTION_EDGE_URL = os.environ.get("ACTION_EDGE_URL", "http://127.0.0.1:8082").rstrip("/")
PUBLIC_EDGE_URL = os.environ.get("PUBLIC_EDGE_URL", "http://127.0.0.1:8080").rstrip("/")
GATEKEEPER_BASE_URL = os.environ.get("GATEKEEPER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
TIMEOUT = float(os.environ.get("DIAGNOSTIC_TIMEOUT_SECONDS", "5"))


def request(method, url, body=None, headers=None):
    encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Accept": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, parse(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, parse(raw)
    except urllib.error.URLError as exc:
        return None, {"error": "unreachable", "detail": str(exc.reason)}


def parse(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw[:500]}


def print_result(label, status, body):
    print(json.dumps({"probe": label, "status": status, "body": body}, separators=(",", ":")))


def unsigned_payload():
    return {
        "artifact_ref": "sha256:" + ("0" * 64),
        "url": "https://example.com/",
        "intent": "diagnostic unsigned request",
    }


def is_missing_auth(status, body):
    return (
        status == 401
        and isinstance(body, dict)
        and body.get("error") == "missing_agent_auth"
    )


def classify_summary(
    action_health_status,
    direct_unsigned_status,
    direct_unsigned_body,
    gatekeeper_status,
    gatekeeper_mount_ok,
    public_unsigned_status,
    public_unsigned_body,
    signed_status,
    signed_body,
):
    public_reaches_action = is_missing_auth(public_unsigned_status, public_unsigned_body)
    direct_action_boundary_ok = is_missing_auth(direct_unsigned_status, direct_unsigned_body)
    gatekeeper_direct_ok = gatekeeper_status == 200 and gatekeeper_mount_ok

    if action_health_status != 200:
        return {
            "status": "BLOCKED",
            "boundary": "action_edge_process",
            "reason": "action-edge health probe failed",
        }

    if not direct_action_boundary_ok:
        return {
            "status": "BLOCKED",
            "boundary": "action_edge_direct_post",
            "reason": "direct unsigned POST did not reach the expected missing_agent_auth boundary",
        }

    if not public_reaches_action:
        return {
            "status": "BLOCKED",
            "boundary": "public_edge_to_action_edge",
            "reason": "public unsigned POST did not reach action-edge authentication",
        }

    if not gatekeeper_direct_ok:
        return {
            "status": "BLOCKED",
            "boundary": "gatekeeper_direct",
            "reason": "direct Gatekeeper health or parent-shield route mount is unavailable",
        }

    if signed_status == "SKIPPED":
        return {
            "status": "READY_FOR_SIGNED_PROBE",
            "boundary": "action_edge_to_gatekeeper",
            "reason": "edge boundaries and direct V2 health are proven; signed credentials/artifact are required to reproduce the remaining hop",
        }

    if signed_status == 502:
        detail = signed_body.get("detail") if isinstance(signed_body, dict) else None
        return {
            "status": "REPRODUCED",
            "boundary": "action_edge_to_gatekeeper",
            "reason": "signed request passed public/action authentication but action-edge reported Gatekeeper unreachable",
            "detail": detail,
            "topology_warning": (
                "Direct V2 health from this diagnostic process does not prove that "
                "GATEKEEPER_BASE_URL is reachable from the action-edge process namespace."
            ),
        }

    if signed_status is None:
        return {
            "status": "BLOCKED",
            "boundary": "diagnostic_to_public_edge",
            "reason": "signed request could not reach the public edge",
        }

    return {
        "status": "SIGNED_PROBE_COMPLETED",
        "boundary": "action_edge_to_gatekeeper",
        "signed_status": signed_status,
        "reason": "signed request did not reproduce the prior 502",
    }


def main():
    failures = 0

    action_health_status, action_health_body = request("GET", f"{ACTION_EDGE_URL}/health")
    print_result("action_edge_health", action_health_status, action_health_body)
    if action_health_status != 200:
        failures += 1

    direct_unsigned_status, direct_unsigned_body = request(
        "POST",
        f"{ACTION_EDGE_URL}/api/v2/actions/navigation",
        unsigned_payload(),
        {"Content-Type": "application/json"},
    )
    print_result("action_edge_missing_auth_direct", direct_unsigned_status, direct_unsigned_body)
    if not is_missing_auth(direct_unsigned_status, direct_unsigned_body):
        failures += 1

    gatekeeper_status, gatekeeper_body = request("GET", f"{GATEKEEPER_BASE_URL}/health")
    print_result("gatekeeper_health_direct", gatekeeper_status, gatekeeper_body)
    gatekeeper_mount_ok = False
    if gatekeeper_status != 200:
        failures += 1
    else:
        mounts = gatekeeper_body.get("routeMounts") if isinstance(gatekeeper_body, dict) else None
        gatekeeper_mount_ok = isinstance(mounts, list) and "parent-shield" in mounts
        if not gatekeeper_mount_ok:
            failures += 1
            print_result(
                "gatekeeper_parent_shield_mount",
                409,
                {"error": "required_route_missing", "routeMounts": mounts},
            )

    public_unsigned_status, public_unsigned_body = request(
        "POST",
        f"{PUBLIC_EDGE_URL}/api/v2/actions/navigation",
        unsigned_payload(),
        {"Content-Type": "application/json"},
    )
    print_result("public_edge_missing_auth", public_unsigned_status, public_unsigned_body)
    if not is_missing_auth(public_unsigned_status, public_unsigned_body):
        failures += 1

    agent_id = os.environ.get("DIAGNOSTIC_AGENT_ID")
    secret = os.environ.get("DIAGNOSTIC_AGENT_SECRET")
    artifact_ref = os.environ.get("DIAGNOSTIC_ARTIFACT_REF")
    target_url = os.environ.get("DIAGNOSTIC_TARGET_URL", "https://example.com/")

    signed_status = "SKIPPED"
    signed_body = {
        "reason": "set DIAGNOSTIC_AGENT_ID, DIAGNOSTIC_AGENT_SECRET, and DIAGNOSTIC_ARTIFACT_REF",
        "secret_printed": False,
    }

    if agent_id and secret and artifact_ref:
        signed = {
            "artifact_ref": artifact_ref,
            "url": target_url,
            "intent": "diagnostic signed request",
        }
        raw = json.dumps(signed, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        timestamp = str(int(time.time()))
        canonical = f"{agent_id}\n{timestamp}\n{digest}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            f"{PUBLIC_EDGE_URL}/api/v2/actions/navigation",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Id": agent_id,
                "X-Agent-Timestamp": timestamp,
                "X-Agent-Signature": signature,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
                signed_status = response.status
                signed_body = parse(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            signed_status = exc.code
            signed_body = parse(exc.read().decode("utf-8", errors="replace"))
        except urllib.error.URLError as exc:
            signed_status = None
            signed_body = {"error": "unreachable", "detail": str(exc.reason)}

        if signed_status == 502:
            failures += 1

    print_result("public_edge_signed_action", signed_status, signed_body)

    summary = classify_summary(
        action_health_status,
        direct_unsigned_status,
        direct_unsigned_body,
        gatekeeper_status,
        gatekeeper_mount_ok,
        public_unsigned_status,
        public_unsigned_body,
        signed_status,
        signed_body,
    )
    print_result("diagnosis", 200 if summary["status"] not in {"BLOCKED", "REPRODUCED"} else 409, summary)

    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
