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
TENKI_DERIVE_URL = os.environ.get(
    "TENKI_DERIVE_URL",
    os.environ.get("TENKI_STEWARD_URL", ""),
).strip()
TENKI_STEWARD_TIMEOUT = float(os.environ.get("TENKI_STEWARD_TIMEOUT", "20"))

NON_AUTHORITY_FIELDS = {
    "authority",
    "permit",
    "capability",
    "token",
    "gatekeeper_verdict",
}


def _artifact_digest(artifact_ref):
    if (
        not isinstance(artifact_ref, str)
        or not artifact_ref.startswith("sha256:")
        or len(artifact_ref) != 71
    ):
        raise RuntimeError("Tenki derive requires a canonical sha256 ArtifactRef")
    digest = artifact_ref.split(":", 1)[1].lower()
    if any(char not in "0123456789abcdef" for char in digest):
        raise RuntimeError("Tenki derive ArtifactRef digest must be lowercase hexadecimal")
    return digest


def build_derive_request(artifact_ref, requested_effect, principal):
    """Build the exact verified Tenki /derive request for the current governed run."""
    digest = _artifact_digest(artifact_ref)
    if not isinstance(requested_effect, str) or not requested_effect:
        raise RuntimeError("Tenki derive requires the current requested_effect")
    if not isinstance(principal, str) or not principal:
        raise RuntimeError("Tenki derive requires the current principal")
    return {
        "artifact_ref": artifact_ref,
        "artifact_sha256": digest,
        "requested_effect": requested_effect,
        "principal": principal,
    }


def build_swarm_plan(artifact_ref, requested_effect, principal):
    """Build OASSE swarm provenance around the verified Tenki derive call."""
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
        "requested_effect": requested_effect,
        "principal": principal,
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
        "claim": None,
        "aggregate": None,
    }


def _assert_non_authoritative(value, path="$"):
    """Reject authority-like assertions anywhere in a Tenki/Steward payload."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in NON_AUTHORITY_FIELDS and child not in (None, False):
                raise RuntimeError(
                    f"Tenki/Steward response attempted to assert authority at {child_path}"
                )
            _assert_non_authoritative(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_non_authoritative(child, f"{path}[{index}]")


def _normalize_worker_response(plan, payload, elapsed_ms, source="live_http"):
    """Normalize the verified Tenki derive response without changing its raw shape."""
    if not isinstance(payload, dict):
        raise RuntimeError("Tenki derive response must be a JSON object")

    _assert_non_authoritative(payload)

    if payload.get("ok") is not True:
        raise RuntimeError("Tenki derive response did not report ok=true")

    claim = payload.get("claim")
    if not isinstance(claim, dict):
        raise RuntimeError("Tenki derive response must contain a claim object")

    if claim.get("authority") is not False:
        raise RuntimeError("Tenki derived claim must explicitly set authority=false")
    if claim.get("artifact_ref") != plan["artifact_ref"]:
        raise RuntimeError("Tenki derived claim artifact_ref does not match governed ArtifactRef")
    if claim.get("artifact_sha256") != _artifact_digest(plan["artifact_ref"]):
        raise RuntimeError("Tenki derived claim artifact_sha256 does not match governed ArtifactRef")
    if claim.get("requested_effect") != plan["requested_effect"]:
        raise RuntimeError("Tenki derived claim requested_effect does not match current governed effect")
    if claim.get("principal") != plan["principal"]:
        raise RuntimeError("Tenki derived claim principal does not match current principal")
    if claim.get("compute_plane") != "tenki":
        raise RuntimeError("Tenki derived claim must identify compute_plane=tenki")
    if claim.get("role") != "derived_claim_only":
        raise RuntimeError("Tenki derived claim must remain derived_claim_only")

    return {
        "status": "LIVE",
        "live": True,
        "platform": "Tenki",
        "snapshot_id": TENKI_SNAPSHOT_ID,
        "authority": False,
        "plan": plan,
        "elapsed_ms": round(elapsed_ms, 2),
        "source": source,
        "workers": [],
        "claim": claim,
        "aggregate": None,
        "raw": payload,
    }


def run_tenki_swarm(artifact_ref, requested_effect, principal):
    plan = build_swarm_plan(artifact_ref, requested_effect, principal)
    derive_request = build_derive_request(artifact_ref, requested_effect, principal)

    if not TENKI_DERIVE_URL:
        return _pending(
            plan,
            "TENKI_DERIVE_URL is unset; live Tenki is verified but this runtime cannot reach /derive.",
        )

    request_body = json.dumps(derive_request, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        TENKI_DERIVE_URL,
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
        return _pending(plan, f"Tenki derive HTTP {exc.code}: {detail[-800:]}")
    except (urllib.error.URLError, TimeoutError) as exc:
        return _pending(plan, f"Tenki derive unavailable: {exc}")

    elapsed_ms = (time.perf_counter() - started) * 1000
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Tenki derive returned non-JSON response") from exc

    return _normalize_worker_response(plan, payload, elapsed_ms)
