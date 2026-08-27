import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from arena import run_arena

PORT = int(os.environ.get("DEMO_ORCHESTRATOR_PORT", "8083"))

ARTIFACT_URL = os.environ.get(
    "ARTIFACT_BOUNDARY_URL",
    "http://127.0.0.1:8081/api/v2/artifacts"
)

ACTION_URL = os.environ.get(
    "ACTION_EDGE_URL",
    "http://127.0.0.1:8082/api/v2/actions/navigation"
)

try:
    AGENT_KEYS = json.loads(
        os.environ.get("GATEKEEPER_AGENT_KEYS_JSON", "{}")
    )
except json.JSONDecodeError as exc:
    raise RuntimeError("GATEKEEPER_AGENT_KEYS_JSON must be valid JSON") from exc

for agent_id in ("agent-a", "agent-b"):
    if not isinstance(AGENT_KEYS.get(agent_id), str):
        raise RuntimeError(f"{agent_id} must have a string signing key")


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
        "to": "agent-b",
        "artifact_ref": artifact_ref,
        "authority_transferred": False
    })

    agent_b_headers = {
        "Content-Type": "application/json",
        **signature_headers("agent-b", action_raw)
    }

    agent_b_status, agent_b_result = request_json(
        ACTION_URL,
        action_raw,
        agent_b_headers
    )

    timeline.append({
        "stage": "agent_b_action",
        "principal": "agent-b",
        "artifact_ref": artifact_ref,
        "status": agent_b_status,
        "result": agent_b_result
    })

    gatekeeper = agent_b_result.get("gatekeeper", {})

    return {
        "ok": (
            agent_a_status == 403
            and agent_b_status == 200
            and agent_b_result.get("authority_transfer_from_artifact") is False
        ),
        "run_id": run_id,
        "thesis": "The artifact can move. Authority cannot.",
        "artifact_ref": artifact_ref,
        "agent_a": {
            "authenticated": agent_a_status == 403,
            "authorized": False,
            "status": agent_a_status
        },
        "agent_b": {
            "authenticated": agent_b_status == 200,
            "authorized_to_request": agent_b_status == 200,
            "status": agent_b_status
        },
        "authority_transfer_from_artifact": False,
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
    server_version = "GatekeeperDemoOrchestrator/0.3"

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
                "arena": True
            })

        return self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path not in ("/api/demo/run", "/api/demo/arena"):
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
