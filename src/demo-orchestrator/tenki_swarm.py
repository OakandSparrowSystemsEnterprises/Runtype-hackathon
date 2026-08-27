import json
import os
import time
import urllib.error
import urllib.request
import uuid

TENKI_SNAPSHOT_ID = os.environ.get(
    "TENKI_STEWARD_SNAPSHOT_ID",
    "07fd77b8-7caf-400e-8e8e-42eb16396098",
)
TENKI_STEWARD_URL = os.environ.get("TENKI_STEWARD_URL", "").strip()
TENKI_STEWARD_TIMEOUT = float(os.environ.get("TENKI_STEWARD_TIMEOUT", "20"))


def build_swarm_plan(artifact_ref):
    """Build the OASSE-owned orchestration contract, not a Tenki API payload."""
    plan_id = uuid.uuid4().hex
    jobs = [
        {
            "job_id": f"{plan_id}:goi-state",
            "worker_role": "goi-derived-state",
            "artifact_ref": artifact_ref,
            "authority": False,
        },
        {
            "job_id": f"{plan_id}:provenance",
            "worker_role": "provenance-summary",
            "artifact_ref": artifact_ref,
            "authority": False,
        },
        {
            "job_id": f"{plan_id}:timing",
            "worker_role": "timing-summary",
            "artifact_ref": artifact_ref,
            "authority": False,
        },
    ]
    return {
        "contract": "oasse.deterministic-steward.swarm-plan.v1",
        "plan_id": plan_id,
        "artifact_ref": artifact_ref,
        "authority": False,
        "jobs": jobs,
    }


def _pending(plan, reason):
    return {
        "status": "NEXT_PENDING",
        "live": False,
        "platform": "Tenki",
        "snapshot_id": TENKI_SNAPSHOT_ID,
        "authority": False,
        "plan": plan,
        "reason": reason,
        "workers": [],
        "aggregate": None,
    }


def _normalize_worker_response(plan, payload, elapsed_ms):
    """
    Normalize an OASSE Steward response after a real Tenki-hosted worker endpoint
    exists. The upstream payload is retained verbatim under `raw` so this module
    never invents or silently reshapes Tenki's live response contract.
    """
    if not isinstance(payload, dict):
        raise RuntimeError("Tenki Steward response must be a JSON object")

    authority_fields = ("authority", "permit", "capability", "gatekeeper_verdict")
    if any(payload.get(field) not in (None, False) for field in authority_fields):
        raise RuntimeError("Tenki/Steward response attempted to assert authority")

    return {
        "status": "LIVE",
        "live": True,
        "platform": "Tenki",
        "snapshot_id": TENKI_SNAPSHOT_ID,
        "authority": False,
        "plan": plan,
        "elapsed_ms": round(elapsed_ms, 2),
        "workers": payload.get("workers", []),
        "aggregate": payload.get("aggregate"),
        "raw": payload,
    }


def run_tenki_swarm(artifact_ref):
    plan = build_swarm_plan(artifact_ref)

    if not TENKI_STEWARD_URL:
        return _pending(
            plan,
            "TENKI_STEWARD_URL is unset; repository contract is ready but live "
            "snapshot execution has not been captured yet.",
        )

    request_body = json.dumps(
        {
            "contract": "oasse.deterministic-steward.swarm-request.v1",
            "plan": plan,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    request = urllib.request.Request(
        TENKI_STEWARD_URL,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TENKI_STEWARD_TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return _pending(plan, f"Tenki Steward HTTP {exc.code}: {detail[-800:]}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return _pending(plan, f"Tenki Steward unavailable: {exc}")

    elapsed_ms = (time.perf_counter() - started) * 1000
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Tenki Steward returned non-JSON response") from exc

    return _normalize_worker_response(plan, payload, elapsed_ms)
