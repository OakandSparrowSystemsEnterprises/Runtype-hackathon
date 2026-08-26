import hashlib
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_DIR = Path(os.environ.get("ARTIFACT_DATA_DIR", "/data"))
OBJECT_DIR = DATA_DIR / "objects"
META_DIR = DATA_DIR / "metadata"
MAX_BYTES = int(os.environ.get("ARTIFACT_MAX_BYTES", 10 * 1024 * 1024))

OBJECT_DIR.mkdir(parents=True, exist_ok=True)
META_DIR.mkdir(parents=True, exist_ok=True)


class ArtifactHandler(BaseHTTPRequestHandler):
    server_version = "GatekeeperArtifactBoundary/0.1"

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
                "service": "gatekeeper-universal-artifact-boundary"
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

        # Identity is established from the original bytes before interpretation.
        digest = hashlib.sha256(raw).hexdigest()
        artifact_ref = f"sha256:{digest}"

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
            "parent_artifact_ref": self.headers.get("X-Artifact-Parent")
        }

        if not meta_path.exists():
            metadata = {
                "artifact_ref": artifact_ref,
                "sha256": digest,
                "size_bytes": len(raw),
                "mime_declared": self.headers.get("Content-Type"),
                "mime_detected": None,
                "parent_artifact_ref": self.headers.get("X-Artifact-Parent"),
                "identity": {
                    "principal": None,
                    "verification": "not-yet-bound"
                },
                "created_unix_ms": now_ms,
                "observations": [observation],
                "authority": {
                    "content_grants_authority": False
                }
            }
        else:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))

            if "observations" not in metadata:
                metadata["observations"] = [{
                    "observed_unix_ms": metadata.get("created_unix_ms"),
                    "mime_declared": metadata.get("mime_declared"),
                    "parent_artifact_ref": metadata.get("parent_artifact_ref")
                }]

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


