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


def main():
    failures = 0

    status, body = request("GET", f"{ACTION_EDGE_URL}/health")
    print_result("action_edge_health", status, body)
    if status != 200:
        failures += 1

    status, body = request("GET", f"{GATEKEEPER_BASE_URL}/health")
    print_result("gatekeeper_health_direct", status, body)
    if status != 200:
        failures += 1
    else:
        mounts = body.get("routeMounts") if isinstance(body, dict) else None
        if not isinstance(mounts, list) or "parent-shield" not in mounts:
            failures += 1
            print_result(
                "gatekeeper_parent_shield_mount",
                409,
                {"error": "required_route_missing", "routeMounts": mounts},
            )

    unsigned = {
        "artifact_ref": "sha256:" + ("0" * 64),
        "url": "https://example.com/",
        "intent": "diagnostic unsigned request",
    }
    status, body = request(
        "POST",
        f"{PUBLIC_EDGE_URL}/api/v2/actions/navigation",
        unsigned,
        {"Content-Type": "application/json"},
    )
    print_result("public_edge_missing_auth", status, body)
    if status != 401 or not isinstance(body, dict) or body.get("error") != "missing_agent_auth":
        failures += 1

    agent_id = os.environ.get("DIAGNOSTIC_AGENT_ID")
    secret = os.environ.get("DIAGNOSTIC_AGENT_SECRET")
    artifact_ref = os.environ.get("DIAGNOSTIC_ARTIFACT_REF")
    target_url = os.environ.get("DIAGNOSTIC_TARGET_URL", "https://example.com/")
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
        print_result("public_edge_signed_action", signed_status, signed_body)
        if signed_status == 502:
            failures += 1
    else:
        print_result(
            "public_edge_signed_action",
            "SKIPPED",
            {
                "reason": "set DIAGNOSTIC_AGENT_ID, DIAGNOSTIC_AGENT_SECRET, and DIAGNOSTIC_ARTIFACT_REF",
                "secret_printed": False,
            },
        )

    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
