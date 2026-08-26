import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_DIR = Path(os.environ.get("ARTIFACT_DATA_DIR", "/data"))
OBJECT_DIR = DATA_DIR / "objects"
META_DIR = DATA_DIR / "metadata"
MAX_BYTES = int(os.environ.get("ARTIFACT_MAX_BYTES", 10 * 1024 * 1024))
AUTH_MAX_SKEW_SECONDS = int(os.environ.get("AGENT_AUTH_MAX_SKEW_SECONDS", "300"))

try:
    AGENT_KEYS = json.loads(os.environ.get("GATEKEEPER_AGENT_KEYS_JSON", "{}"))
except json.JSONDecodeError:
    raise RuntimeError("GATEKEEPER_AGENT_KEYS_JSON must be valid JSON")

OBJECT_DIR.mkdir(parents=True, exist_ok=True)
META_DIR.mkdir(parents=True, exist_ok=True)


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

    now = int(time.time())

    if abs(now - timestamp) > AUTH_MAX_SKEW_SECONDS:
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


class ArtifactHandler(BaseHTTPRequestHandler):
    server_version = "GatekeeperArtifactBoundary/0.2"

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
                "service": "gatekeeper-universal-artifact-boundary",
                "agent_auth": "hmac-sha256"
            })

        if self.path.startswith("/api/v2/artifacts/"):
            digest = self.path.rsplit("/", 1)[-1].lower()

            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                return self.send_json(400, {"error": "invalid_sha256"})

            meta_path = META_DIR / f"{digest}.json"

            if not meta_path.exists():
                return self.send_json(404, {"error": "artifact_not_found"})

            return self.send_json(
                200,
                json.loads(meta_path.read_text(encoding="utf-8"))
            )

        return self.send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/api/v2/artifacts":
            return self.send_json(404, {"error": "not_found"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json(400, {"error": "invalid_content_length"})

        if length <= 0:
            return self.send_json(400, {"error": "empty_artifact"})

        if length > MAX_BYTES:
            return self.send_json(413, {
                "error": "artifact_too_large",
                "max_bytes": MAX_BYTES
            })

        raw = self.rfile.read(length)

        if len(raw) != length:
            return self.send_json(400, {"error": "incomplete_artifact"})

        # Establish artifact identity from the exact original bytes first.
        digest = hashlib.sha256(raw).hexdigest()
        artifact_ref = f"sha256:{digest}"

        # Authentication is bound to that exact byte identity.
        identity, auth_error = verify_agent(self.headers, digest)

        if auth_error:
            return self.send_json(401, {
                "error": auth_error,
                "artifact_sha256": digest
            })

        object_path = OBJECT_DIR / digest
        meta_path = META_DIR / f"{digest}.json"

        if not object_path.exists():
            temp_path = OBJECT_DIR / f".{digest}.tmp"
            temp_path.write_bytes(raw)
            temp_path.replace(object_path)

        now_ms = int(time.time() * 1000)

        observation = {
            "observed_unix_ms": now_ms,
            "mime_declared": self.headers.get("Content-Type"),
            "parent_artifact_ref": self.headers.get("X-Artifact-Parent"),
            "identity": identity
        }

        if not meta_path.exists():
            metadata = {
                "artifact_ref": artifact_ref,
                "sha256": digest,
                "size_bytes": len(raw),
                "mime_declared": self.headers.get("Content-Type"),
                "mime_detected": None,
                "parent_artifact_ref": self.headers.get("X-Artifact-Parent"),
                "identity": identity,
                "created_unix_ms": now_ms,
                "observations": [observation],
                "authority": {
                    "content_grants_authority": False
                }
            }
        else:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))

            if "observations" not in metadata:
                metadata["observations"] = []

            metadata["observations"].append(observation)

        meta_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8"
        )

        self.send_json(201, metadata)

    def log_message(self, format, *args):
        print(
            "%s - - [%s] %s"
            % (self.client_address[0], self.log_date_time_string(), format % args),
            flush=True
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8081"))
    server = ThreadingHTTPServer(("0.0.0.0", port), ArtifactHandler)
    print(f"Universal Artifact Boundary listening on :{port}", flush=True)
    server.serve_forever()
