import json
import os
import urllib.error
import urllib.request
import uuid

GATEKEEPER_BASE = os.environ.get("GATEKEEPER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
CHAIN_VERIFY_PATH = "/api/v1/chain/verify"


def _request_json(method, path, *, headers=None, timeout=20):
    request = urllib.request.Request(
        f"{GATEKEEPER_BASE}{path}",
        headers=dict(headers or {}),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def run_chain_verification_probe():
    key = f"arena-chain-verify-{uuid.uuid4().hex}"
    status, payload = _request_json(
        "GET",
        CHAIN_VERIFY_PATH,
        headers={
            "X-Idempotency-Key": key,
            "X-Case-Id": "hackathon-v2-chain-verify",
        },
    )

    artifact = payload.get("artifact") if isinstance(payload, dict) else None
    if not isinstance(artifact, dict):
        artifact = {}

    verification_ok = payload.get("ok") is True if isinstance(payload, dict) else False
    problems = payload.get("problems") if isinstance(payload, dict) else None
    if not isinstance(problems, list):
        problems = []

    return {
        "ok": (
            status == 200
            and verification_ok
            and not problems
            and bool(artifact.get("gate1_hash"))
            and bool(artifact.get("gate2_hash"))
            and bool(artifact.get("result_hash"))
            and bool(artifact.get("artifact_hash"))
        ),
        "status": status,
        "verified": verification_ok,
        "checked": payload.get("checked") if isinstance(payload, dict) else None,
        "broken_at": payload.get("broken_at") if isinstance(payload, dict) else None,
        "problems": problems,
        "stored_tip": payload.get("stored_tip") if isinstance(payload, dict) else None,
        "computed_tip": payload.get("computed_tip") if isinstance(payload, dict) else None,
        "snapshot_hash": payload.get("snapshot_hash") if isinstance(payload, dict) else None,
        "artifact": {
            "id": artifact.get("id"),
            "gate1_hash": artifact.get("gate1_hash"),
            "gate2_hash": artifact.get("gate2_hash"),
            "result_hash": artifact.get("result_hash"),
            "artifact_hash": artifact.get("artifact_hash"),
        },
    }


def run_idempotency_probe():
    key = f"arena-idempotency-{uuid.uuid4().hex}"
    headers = {
        "X-Idempotency-Key": key,
        "X-Case-Id": "hackathon-v2-idempotency",
    }

    first_status, first_payload = _request_json(
        "GET",
        CHAIN_VERIFY_PATH,
        headers=headers,
    )
    replay_status, replay_payload = _request_json(
        "GET",
        CHAIN_VERIFY_PATH,
        headers=headers,
    )

    first_artifact = first_payload.get("artifact") if isinstance(first_payload, dict) else None
    if not isinstance(first_artifact, dict):
        first_artifact = {}

    detail = replay_payload.get("detail") if isinstance(replay_payload, dict) else None
    if not isinstance(detail, dict):
        detail = {}
    replay_artifact = detail.get("artifact")
    if not isinstance(replay_artifact, dict):
        replay_artifact = {}

    same_artifact = bool(
        first_artifact.get("id")
        and first_artifact.get("id") == replay_artifact.get("id")
        and first_artifact.get("artifact_hash") == replay_artifact.get("artifact_hash")
    )
    replay_outcome = detail.get("outcome")

    return {
        "ok": (
            first_status == 200
            and replay_status == 409
            and replay_outcome == "idempotent-ledger-read-already-resolved"
            and same_artifact
        ),
        "key": key,
        "first_status": first_status,
        "replay_status": replay_status,
        "replay_outcome": replay_outcome,
        "same_artifact": same_artifact,
        "first_artifact": {
            "id": first_artifact.get("id"),
            "artifact_hash": first_artifact.get("artifact_hash"),
        },
        "replay_artifact": {
            "id": replay_artifact.get("id"),
            "artifact_hash": replay_artifact.get("artifact_hash"),
        },
    }
