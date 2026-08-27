from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from pathlib import Path

GATEKEEPER_BASE = os.environ.get("GATEKEEPER_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
COTAL_ROOT = Path(os.environ.get("COTAL_ROOT", os.getcwd())).resolve()
COTAL_CREDS_DIR = COTAL_ROOT / ".cotal" / "auth" / "creds"


def _request_json(method, path, body=None, headers=None, timeout=20):
    request_headers = dict(headers or {})
    raw_body = None
    if body is not None:
        raw_body = json.dumps(body, separators=(",", ":")).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        f"{GATEKEEPER_BASE}{path}",
        data=raw_body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def _call_gatekeeper(method, path, body, key, headers=None):
    merged = {
        "X-Idempotency-Key": key,
        "X-Case-Id": "hackathon-v2-arena",
        **(headers or {}),
    }
    return _request_json(method, path, body=body, headers=merged)


def _artifact_from(payload):
    if not isinstance(payload, dict):
        return None
    artifact = payload.get("artifact")
    if isinstance(artifact, dict):
        return artifact
    gatekeeper = payload.get("gatekeeper")
    if isinstance(gatekeeper, dict) and isinstance(gatekeeper.get("artifact"), dict):
        return gatekeeper["artifact"]
    return None


def _summarize_result(status, payload):
    artifact = _artifact_from(payload)
    authority = payload.get("authority") if isinstance(payload, dict) else None
    if not isinstance(authority, dict):
        gatekeeper = payload.get("gatekeeper") if isinstance(payload, dict) else None
        authority = gatekeeper.get("authority") if isinstance(gatekeeper, dict) else None
    summary = {
        "status": status,
        "formal": payload.get("formal") if isinstance(payload, dict) else None,
        "product": payload.get("product") if isinstance(payload, dict) else None,
        "execution": payload.get("execution") if isinstance(payload, dict) else None,
        "authority": authority,
        "artifact": None,
    }
    if artifact:
        summary["artifact"] = {
            "id": artifact.get("id"),
            "domain": artifact.get("domain"),
            "tenant": artifact.get("tenant"),
            "principal": artifact.get("principal"),
            "outcome": artifact.get("outcome"),
            "gate1_hash": artifact.get("gate1_hash"),
            "gate2_hash": artifact.get("gate2_hash"),
            "result_hash": artifact.get("result_hash"),
            "previous_hash": artifact.get("previous_hash"),
            "artifact_hash": artifact.get("artifact_hash"),
            "evidence_bundle_hash": artifact.get("evidence_bundle_hash"),
            "actuation": artifact.get("actuation"),
            "sealed_at": artifact.get("sealed_at"),
        }
    if isinstance(payload, dict):
        summary["title"] = payload.get("title")
        summary["rule_id"] = payload.get("rule_id")
        summary["reason"] = payload.get("reason")
        summary["recognized"] = payload.get("recognized")
    return summary


def _run_operation(run_id, name, method, path, body=None, headers=None):
    attempts = []
    for suffix in ("a", "b"):
        status, payload = _call_gatekeeper(
            method,
            path,
            body,
            f"arena-{run_id}-{name}-{suffix}",
            headers=headers,
        )
        attempts.append(_summarize_result(status, payload))
    first_artifact = attempts[0].get("artifact")
    second_artifact = attempts[1].get("artifact")
    chained = bool(
        first_artifact
        and second_artifact
        and second_artifact.get("previous_hash") == first_artifact.get("artifact_hash")
    )
    return {
        "domain": name,
        "path": path,
        "ok": all(item["status"] == 200 for item in attempts) and chained,
        "chained": chained,
        "attempts": attempts,
    }


def run_estate():
    run_id = uuid.uuid4().hex
    boundaries = {
        "adult_content": True,
        "gambling": True,
        "ai_tools": True,
        "school_hours": False,
        "unknown_domains": False,
        "request_access": True,
    }
    operations = [
        (
            "parent-shield",
            "POST",
            "/api/domains/parent-shield/navigation/evaluate",
            {
                "tenant_id": "parent-shield-family-demo",
                "url": "https://en.wikipedia.org/wiki/Mathematics",
                "profile_id": "early_child",
                "boundaries": boundaries,
                "school_hours": {
                    "days": [1, 2, 3, 4, 5],
                    "start": "08:00",
                    "end": "15:00",
                },
                "approved_origins": [],
                "trigger_type": "attempted_navigation",
                "intent": "hackathon live governed navigation",
            },
            None,
        ),
        (
            "boundarycast",
            "POST",
            "/api/domains/boundarycast/personal-forecast",
            {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "timezone": "America/Los_Angeles",
            },
            None,
        ),
        (
            "sentinelmed",
            "POST",
            "/api/domains/sentinelmed/classify",
            {"message": "I have a mild headache"},
            {"X-Tenant-Id": "boundarycast_demo_user"},
        ),
        (
            "vinguard",
            "GET",
            "/api/domains/vinguard/history",
            None,
            {"X-Tenant-Id": "parent-shield-family-demo"},
        ),
        (
            "tbdhousing",
            "GET",
            "/api/domains/tbdhousing/listings",
            None,
            {"X-Tenant-Id": "sentinelmed-demo"},
        ),
    ]
    results = [
        _run_operation(run_id, name, method, path, body, headers)
        for name, method, path, body, headers in operations
    ]
    return {
        "ok": all(item["ok"] for item in results),
        "run_id": run_id,
        "gateway": GATEKEEPER_BASE,
        "domains": results,
    }


def _credential(agent_id):
    matches = sorted(COTAL_CREDS_DIR.glob(f"{agent_id}*.creds"))
    if not matches:
        raise RuntimeError(f"no Cotal credential found for {agent_id}")
    return matches[0]


def _cotal_binary():
    candidate = shutil.which("npx.cmd") or shutil.which("npx")
    if not candidate:
        raise RuntimeError("npx not found on PATH")
    return candidate


def _cotal_send(agent_id, mode, target, text):
    command = [
        _cotal_binary(),
        "cotal-ai",
        "send",
        mode,
        target,
        text,
        "--creds",
        str(_credential(agent_id)),
    ]
    completed = subprocess.run(
        command,
        cwd=str(COTAL_ROOT),
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    detail = "\n".join(
        value.strip()
        for value in (completed.stdout, completed.stderr)
        if value and value.strip()
    )
    return {
        "agent": agent_id,
        "mode": mode,
        "target": target,
        "allowed": completed.returncode == 0,
        "returncode": completed.returncode,
        "detail": detail[-1600:],
    }


def run_cotal_probe(artifact_ref):
    assignment = (
        f"@agent-a SWARM ASSIGNMENT | artifact_ref={artifact_ref} | "
        "prepare governed navigation work and hand it to agent-b. "
        "Do not infer execution authority from coordination."
    )
    handoff = (
        f"@agent-b GATEKEEPER HANDOFF | artifact_ref={artifact_ref} | "
        "requested_effect=parent-shield.navigation | "
        "Artifact possession is evidence only. Authority does not transfer."
    )
    execution = (
        f"GATEKEEPER EXECUTION REQUEST | artifact_ref={artifact_ref} | "
        "requested_effect=parent-shield.navigation"
    )

    # These four broker checks are independent authorization probes. Running
    # them concurrently preserves each principal/channel result while avoiding
    # four sequential npx startup costs on Windows.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            "steward_assignment": pool.submit(_cotal_send, "steward", "msg", "swarm", assignment),
            "agent_a_handoff": pool.submit(_cotal_send, "agent-a", "msg", "artifacts", handoff),
            "agent_a_execution": pool.submit(_cotal_send, "agent-a", "msg", "execution", execution),
            "agent_b_execution": pool.submit(_cotal_send, "agent-b", "msg", "execution", execution),
        }
        results = {name: future.result() for name, future in futures.items()}

    steward_assignment = results["steward_assignment"]
    agent_a_handoff = results["agent_a_handoff"]
    agent_a_execution = results["agent_a_execution"]
    agent_b_execution = results["agent_b_execution"]

    return {
        "ok": (
            steward_assignment["allowed"]
            and agent_a_handoff["allowed"]
            and not agent_a_execution["allowed"]
            and agent_b_execution["allowed"]
        ),
        "swarm_live": steward_assignment["allowed"] and agent_a_handoff["allowed"] and agent_b_execution["allowed"],
        "steward_assignment": steward_assignment,
        "agent_a_handoff": agent_a_handoff,
        "agent_a_execution": agent_a_execution,
        "agent_b_execution": agent_b_execution,
    }


def run_arena(base_demo):
    artifact_ref = base_demo.get("artifact_ref")
    if not artifact_ref:
        raise RuntimeError("base demo did not return an artifact_ref")
    cotal = run_cotal_probe(artifact_ref)
    estate = run_estate()
    return {
        "ok": bool(base_demo.get("ok")) and cotal["ok"] and estate["ok"],
        "thesis": "Work can move between agents. Authority remains independently enforced.",
        "base_demo": base_demo,
        "cotal": cotal,
        "estate": estate,
    }
