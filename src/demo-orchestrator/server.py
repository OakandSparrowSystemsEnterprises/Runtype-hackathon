import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

from arena import run_arena
from evidence_pipeline import run_progressive_evidence

PORT = int(os.environ.get("DEMO_ORCHESTRATOR_PORT", "8083"))

ARTIFACT_URL = os.environ.get(
    "ARTIFACT_BOUNDARY_URL",
    "http://127.0.0.1:8081/api/v2/artifacts"
)

ACTION_URL = os.environ.get(
    "ACTION_EDGE_URL",
    "http://127.0.0.1:8082/api/v2/actions/navigation"
)

REQUESTED_EFFECT = "parent-shield.navigation"
EFFECT_PRINCIPAL = "agent-b"

try:
    AGENT_KEYS = json.loads(
        os.environ.get("GATEKEEPER_AGENT_KEYS_JSON", "{}")
    )
except json.JSONDecodeError as exc:
    raise RuntimeError("GATEKEEPER_AGENT_KEYS_JSON must be valid JSON") from exc

for agent_id in ("agent-a", "agent-b"):
    if not isinstance(AGENT_KEYS.get(agent_id), str):
        raise RuntimeError(f"{agent_id} must have a string signing key")


VERDICT_CACHE = {}
VERDICT_CACHE_LOCK = Lock()
VERDICT_CACHE_LIMIT = 32


def _cache_verdict(result):
    run_id = result.get("run_id") if isinstance(result, dict) else None
    if not run_id:
        return
    with VERDICT_CACHE_LOCK:
        VERDICT_CACHE[run_id] = result
        while len(VERDICT_CACHE) > VERDICT_CACHE_LIMIT:
            oldest = next(iter(VERDICT_CACHE))
            VERDICT_CACHE.pop(oldest, None)


def _get_cached_verdict(run_id):
    with VERDICT_CACHE_LOCK:
        return VERDICT_CACHE.get(run_id)


def signature_headers(agent_id, raw_body, artifact_digest=None):
    timestamp = str(int(time.time()))
    secret = AGENT_KEYS[agent_id]

    digest = (
        artifact_digest
        if artifact_digest is not None
        else hashlib.sha256(raw_body).hexdigest()
    )

    canonical = f"{agent_id}\n{timestamp}\n{digest}".encode("utf-8")

    signature = hmac.new(
        secret.encode("utf-8"),
        canonical,
        hashlib.sha256
    ).hexdigest()

    return {
        "X-Agent-Id": agent_id,
        "X-Agent-Timestamp": timestamp,
        "X-Agent-Signature": signature
    }


def request_json(url, raw_body, headers):
    request = urllib.request.Request(
        url,
        data=raw_body,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}

        return exc.code, parsed


def run_demo(target_url, intent):
    proof_started = time.perf_counter()
    run_id = uuid.uuid4().hex

    timeline = []

    artifact_bytes = f"gatekeeper-agent-demo:{run_id}".encode("utf-8")
    artifact_digest = hashlib.sha256(artifact_bytes).hexdigest()

    artifact_headers = {
        "Content-Type": "application/octet-stream",
        **signature_headers(
            "agent-a",
            artifact_bytes,
            artifact_digest=artifact_digest
        )
    }

    artifact_status, artifact = request_json(
        ARTIFACT_URL,
        artifact_bytes,
        artifact_headers
    )

    if artifact_status not in (200, 201):
        return {
            "ok": False,
            "run_id": run_id,
            "failed_stage": "artifact_ingress",
            "status": artifact_status,
            "response": artifact
        }

    artifact_ref = artifact["artifact_ref"]

    timeline.append({
        "stage": "artifact_created",
        "principal": "agent-a",
        "artifact_ref": artifact_ref,
        "status": artifact_status
    })

    action_payload = {
        "artifact_ref": artifact_ref,
        "url": target_url,
        "intent": intent
    }

    action_raw = json.dumps(
        action_payload,
        separators=(",", ":")
    ).encode("utf-8")

    agent_a_headers = {
        "Content-Type": "application/json",
        **signature_headers("agent-a", action_raw)
    }

    agent_a_status, agent_a_result = request_json(
        ACTION_URL,
        action_raw,
        agent_a_headers
    )

    timeline.append({
        "stage": "agent_a_action",
        "principal": "agent-a",
        "artifact_ref": artifact_ref,
        "status": agent_a_status,
        "result": agent_a_result
    })

    timeline.append({
        "stage": "artifact_handoff",
        "from": "agent-a",
        "to": EFFECT_PRINCIPAL,
        "artifact_ref": artifact_ref,
        "authority_transferred": False
    })

    agent_b_headers = {
        "Content-Type": "application/json",
        **signature_headers(EFFECT_PRINCIPAL, action_raw)
    }

    agent_b_status, agent_b_result = request_json(
        ACTION_URL,
        action_raw,
        agent_b_headers
    )

    timeline.append({
        "stage": "agent_b_action",
        "principal": EFFECT_PRINCIPAL,
        "artifact_ref": artifact_ref,
        "status": agent_b_status,
        "result": agent_b_result
    })

    gatekeeper = agent_b_result.get("gatekeeper", {})
    gatekeeper_latency_ms = agent_b_result.get("gatekeeper_upstream_latency_ms")
    proof_latency_ms = round((time.perf_counter() - proof_started) * 1000, 2)

    return {
        "ok": (
            agent_a_status == 403
            and agent_b_status == 200
            and agent_b_result.get("authority_transfer_from_artifact") is False
        ),
        "run_id": run_id,
        "thesis": "The artifact can move. Authority cannot.",
        "artifact_ref": artifact_ref,
        "requested_effect": REQUESTED_EFFECT,
        "effect_principal": EFFECT_PRINCIPAL,
        "agent_a": {
            "authenticated": agent_a_status == 403,
            "authorized": False,
            "status": agent_a_status
        },
        "agent_b": {
            "principal": EFFECT_PRINCIPAL,
            "authenticated": agent_b_status == 200,
            "authorized_to_request": agent_b_status == 200,
            "status": agent_b_status
        },
        "authority_transfer_from_artifact": False,
        "latency": {
            "gatekeeper_v2_hop_ms": gatekeeper_latency_ms,
            "authority_transfer_proof_ms": proof_latency_ms,
            "gatekeeper_latency_source": "action-edge measured V2 evaluate hop",
            "proof_latency_source": "artifact ingress + A deny + handoff + B governed action"
        },
        "gatekeeper": {
            "formal": gatekeeper.get("formal"),
            "product": gatekeeper.get("product"),
            "execution": gatekeeper.get("execution"),
            "authority": gatekeeper.get("authority"),
            "artifact": gatekeeper.get("artifact")
        },
        "timeline": timeline
    }


class DemoHandler(BaseHTTPRequestHandler):
    server_version = "GatekeeperDemoOrchestrator/0.6"

    def send_json(self, status, payload):
        raw = json.dumps(
            payload,
            separators=(",", ":")
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {
                "status": "ok",
                "service": "gatekeeper-demo-orchestrator",
                "arena": True,
                "progressive_evidence": True,
                "tenki_dynamic_derive": True
            })

        return self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in (
            "/api/demo/run",
            "/api/demo/arena",
            "/api/demo/evidence"
        ):
            return self.send_json(404, {"error": "not_found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"error": "invalid_content_length"})

        if length > 65536:
            return self.send_json(413, {"error": "request_too_large"})

        raw = self.rfile.read(length) if length else b"{}"

        try:
            supplied = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(400, {"error": "invalid_json"})

        if self.path == "/api/demo/evidence":
            run_id = supplied.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                return self.send_json(400, {"error": "run_id_required"})

            base_result = _get_cached_verdict(run_id)
            if base_result is None:
                return self.send_json(404, {
                    "error": "verdict_not_found",
                    "run_id": run_id
                })

            try:
                result = run_progressive_evidence(base_result)
            except Exception as exc:
                return self.send_json(500, {
                    "error": "supporting_evidence_failure",
                    "run_id": run_id,
                    "detail": str(exc)
                })

            return self.send_json(
                200 if result.get("ok") else 500,
                result
            )

        target_url = supplied.get(
            "url",
            "https://en.wikipedia.org/wiki/Math"
        )

        intent = supplied.get(
            "intent",
            "navigate using handed-off artifact"
        )

        arena_requested = (
            self.path == "/api/demo/arena"
            or supplied.get("mode") == "arena"
        )

        try:
            base_result = run_demo(target_url, intent)
            _cache_verdict(base_result)
            result = run_arena(base_result) if arena_requested else base_result
        except Exception as exc:
            return self.send_json(500, {
                "error": "demo_orchestrator_failure",
                "detail": str(exc)
            })

        return self.send_json(
            200 if result.get("ok") else 500,
            result
        )

    def log_message(self, format, *args):
        print(
            "%s - - [%s] %s"
            % (
                self.client_address[0],
                self.log_date_time_string(),
                format % args
            ),
            flush=True
        )


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DemoHandler)
    print(f"Gatekeeper Demo Orchestrator listening on :{PORT}", flush=True)
    server.serve_forever()
