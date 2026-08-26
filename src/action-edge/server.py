import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("ACTION_EDGE_PORT", "8082"))
GATEKEEPER_BASE_URL = os.environ.get(
    "GATEKEEPER_BASE_URL",
    "http://127.0.0.1:8787"
).rstrip("/")

DATA_DIR = Path(os.environ.get("ARTIFACT_DATA_DIR", "/data"))
META_DIR = DATA_DIR / "metadata"

MAX_BODY_BYTES = int(os.environ.get("ACTION_MAX_BYTES", "65536"))
AUTH_MAX_SKEW_SECONDS = int(
    os.environ.get("AGENT_AUTH_MAX_SKEW_SECONDS", "300")
)

CAPABILITY = "parent-shield.navigation"

try:
    AGENT_KEYS = json.loads(
        os.environ.get("GATEKEEPER_AGENT_KEYS_JSON", "{}")
    )
    AGENT_CAPABILITIES = json.loads(
        os.environ.get("GATEKEEPER_AGENT_CAPABILITIES_JSON", "{}")
    )
except json.JSONDecodeError as exc:
    raise RuntimeError("Agent auth environment must contain valid JSON") from exc


def verify_agent(headers, digest):
    agent_id = headers.get("X-Agent-Id")
    timestamp_raw = headers.get("X-Agent-Timestamp")
    signature = headers.get("X-Agent-Signature")

    if not agent_id or not timestamp_raw or not signature:
        return None, "missing_agent_auth"

    secret = AGENT_KEYS.get(agent_id)

    if not secret:
        return None, "unknown_agent"

    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        return None, "invalid_agent_timestamp"

    if abs(int(time.time()) - timestamp) > AUTH_MAX_SKEW_SECONDS:
        return None, "stale_agent_auth"

    canonical = f"{agent_id}\n{timestamp_raw}\n{digest}".encode("utf-8")

    expected = hmac.new(
        secret.encode("utf-8"),
        canonical,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature.lower()):
        return None, "invalid_agent_signature"

    return {
        "principal": agent_id,
        "verification": "hmac-sha256",
        "bound_sha256": digest
    }, None


class ActionHandler(BaseHTTPRequestHandler):
    server_version = "GatekeeperAgentActionEdge/0.1"

    def send_json(self, status, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {
                "status": "ok",
                "service": "gatekeeper-agent-action-edge",
                "capability": CAPABILITY
            })

        return self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/api/v2/actions/navigation":
            return self.send_json(404, {"error": "not_found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"error": "invalid_content_length"})

        if length <= 0:
            return self.send_json(400, {"error": "empty_request"})

        if length > MAX_BODY_BYTES:
            return self.send_json(413, {"error": "request_too_large"})

        raw = self.rfile.read(length)

        if len(raw) != length:
            return self.send_json(400, {"error": "incomplete_request"})

        request_digest = hashlib.sha256(raw).hexdigest()

        identity, auth_error = verify_agent(
            self.headers,
            request_digest
        )

        if auth_error:
            return self.send_json(401, {
                "error": auth_error,
                "request_sha256": request_digest
            })

        agent_id = identity["principal"]
        capabilities = AGENT_CAPABILITIES.get(agent_id, [])

        if CAPABILITY not in capabilities:
            return self.send_json(403, {
                "error": "capability_denied",
                "principal": agent_id,
                "required_capability": CAPABILITY
            })

        try:
            proposed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(400, {"error": "invalid_json"})

        artifact_ref = proposed.get("artifact_ref")

        if (
            not isinstance(artifact_ref, str)
            or not artifact_ref.startswith("sha256:")
            or len(artifact_ref) != 71
        ):
            return self.send_json(400, {"error": "invalid_artifact_ref"})

        artifact_digest = artifact_ref.split(":", 1)[1].lower()

        if not (META_DIR / f"{artifact_digest}.json").exists():
            return self.send_json(404, {
                "error": "artifact_not_found",
                "artifact_ref": artifact_ref
            })

        target_url = proposed.get("url")

        if not isinstance(target_url, str):
            return self.send_json(400, {"error": "invalid_url"})

        parsed = urllib.parse.urlsplit(target_url)

        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return self.send_json(400, {"error": "invalid_url"})

        # These values come from the trusted edge, not agent content.
        gatekeeper_request = {
            "tenant_id": "parent-shield-family-demo",
            "url": target_url,
            "profile_id": "early_child",
            "boundaries": {
                "adult_content": True,
                "ai_tools": True,
                "gambling": True,
                "unknown_domains": False,
                "school_hours": False,
                "request_access": True
            },
            "school_hours": {
                "days": [],
                "start": "08:00",
                "end": "15:00"
            },
            "approved_origins": [],
            "trigger_type": "attempted_navigation",
            "intent": proposed.get(
                "intent",
                "external agent proposed governed navigation"
            ),
            "now_iso": datetime.now(timezone.utc).isoformat()
        }

        encoded = json.dumps(
            gatekeeper_request,
            separators=(",", ":")
        ).encode("utf-8")

        request = urllib.request.Request(
            GATEKEEPER_BASE_URL
            + "/api/domains/parent-shield/navigation/evaluate",
            data=encoded,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                gatekeeper = json.loads(
                    response.read().decode("utf-8")
                )
        except urllib.error.HTTPError as exc:
            detail_raw = exc.read().decode("utf-8", errors="replace")

            try:
                detail = json.loads(detail_raw)
            except json.JSONDecodeError:
                detail = detail_raw

            return self.send_json(exc.code, {
                "error": "gatekeeper_rejected",
                "detail": detail
            })
        except urllib.error.URLError as exc:
            return self.send_json(502, {
                "error": "gatekeeper_unreachable",
                "detail": str(exc.reason)
            })

        return self.send_json(200, {
            "external_identity": identity,
            "capability": CAPABILITY,
            "artifact_ref": artifact_ref,
            "request_sha256": request_digest,
            "authority_transfer_from_artifact": False,
            "gatekeeper": gatekeeper
        })

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
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ActionHandler)
    print(f"Agent Action Edge listening on :{PORT}", flush=True)
    server.serve_forever()
