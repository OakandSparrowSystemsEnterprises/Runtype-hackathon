from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

TENKI_SNAPSHOT_ID = os.environ.get(
    "TENKI_STEWARD_SNAPSHOT_ID",
    "07fd77b8-7caf-400e-8e8e-42eb16396098",
)
TENKI_STEWARD_TIMEOUT = float(os.environ.get("TENKI_STEWARD_TIMEOUT", "20"))
TENKI_SWARM_WIDTH = max(2, min(16, int(os.environ.get("TENKI_SWARM_WIDTH", "4"))))

NON_AUTHORITY_FIELDS = {
    "authority",
    "permit",
    "capability",
    "token",
    "gatekeeper_verdict",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def configured_endpoints():
    raw_many = os.environ.get("TENKI_DERIVE_URLS", "")
    endpoints = [item.strip() for item in raw_many.split(",") if item.strip()]
    if not endpoints:
        single = os.environ.get(
            "TENKI_DERIVE_URL",
            os.environ.get("TENKI_STEWARD_URL", ""),
        ).strip()
        if single:
            endpoints = [single]
    return endpoints


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


def build_swarm_plan(artifact_ref, requested_effect, principal, width=None):
    width = TENKI_SWARM_WIDTH if width is None else int(width)
    seed = {
        "contract": "oasse.tenki.deterministic-replica-swarm.v1",
        "artifact_ref": artifact_ref,
        "requested_effect": requested_effect,
        "principal": principal,
        "replica_width": width,
        "authority": False,
    }
    plan_id = _digest(seed)
    workers = [
        {
            "worker_id": f"{plan_id}:tenki-replica-{index:02d}",
            "replica_index": index,
            "worker_role": "independent-goi-derived-claim-replica",
            "artifact_ref": artifact_ref,
            "authority": False,
        }
        for index in range(width)
    ]
    return {**seed, "plan_id": plan_id, "workers": workers}


def _assert_non_authoritative(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in NON_AUTHORITY_FIELDS and child not in (None, False):
                raise RuntimeError(
                    f"Tenki response attempted to assert authority at {child_path}"
                )
            _assert_non_authoritative(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_non_authoritative(child, f"{path}[{index}]")


def _validate_claim(plan, payload):
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RuntimeError("Tenki derive response did not report ok=true")
    _assert_non_authoritative(payload)
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
    if not isinstance(claim.get("claim_hash"), str) or not claim.get("claim_hash"):
        raise RuntimeError("Tenki derived claim must contain claim_hash")
    return claim


def _run_replica(spec, endpoint, plan, request_body):
    started = time.perf_counter()
    if not endpoint:
        return {
            **spec,
            "status": "PENDING",
            "live": False,
            "authority": False,
            "endpoint_configured": False,
            "claim": None,
            "error": "no distinct Tenki /derive endpoint configured for this replica",
            "elapsed_ms": 0.0,
        }

    request = urllib.request.Request(
        endpoint,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TENKI_STEWARD_TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        claim = _validate_claim(plan, payload)
        status = "COMPLETED"
        live = True
        error = None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        claim = None
        status = "FAILED"
        live = False
        error = f"HTTP {exc.code}: {detail[-800:]}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        claim = None
        status = "FAILED"
        live = False
        error = f"{type(exc).__name__}: {exc}"

    return {
        **spec,
        "status": status,
        "live": live,
        "authority": False,
        "endpoint_configured": True,
        "claim": claim,
        "claim_hash": claim.get("claim_hash") if claim else None,
        "error": error,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def run_tenki_swarm(artifact_ref, requested_effect, principal):
    plan = build_swarm_plan(artifact_ref, requested_effect, principal)
    derive_request = build_derive_request(artifact_ref, requested_effect, principal)
    request_body = json.dumps(derive_request, separators=(",", ":")).encode("utf-8")
    endpoints = configured_endpoints()

    started = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=plan["replica_width"]) as pool:
        futures = []
        for spec in plan["workers"]:
            index = spec["replica_index"]
            endpoint = endpoints[index] if index < len(endpoints) else None
            futures.append(pool.submit(_run_replica, spec, endpoint, plan, request_body))
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item["replica_index"])
    completed = [item for item in results if item["live"]]
    failed = [item for item in results if item["status"] == "FAILED"]
    pending = [item for item in results if item["status"] == "PENDING"]
    claim_hashes = [item.get("claim_hash") for item in completed if item.get("claim_hash")]
    consensus_hash = claim_hashes[0] if claim_hashes and len(set(claim_hashes)) == 1 else None
    consensus = len(completed) >= 2 and consensus_hash is not None
    all_live = len(completed) == plan["replica_width"] and consensus

    semantic_workers = [
        {
            "worker_id": item["worker_id"],
            "replica_index": item["replica_index"],
            "status": item["status"],
            "authority": False,
            "claim_hash": item.get("claim_hash"),
            "error": item.get("error"),
        }
        for item in results
    ]
    aggregate = {
        "replica_width": plan["replica_width"],
        "completed": len(completed),
        "failed": len(failed),
        "pending": len(pending),
        "consensus": consensus,
        "consensus_claim_hash": consensus_hash,
        "authority": False,
        "state_hash": _digest(
            {
                "plan_id": plan["plan_id"],
                "workers": semantic_workers,
                "consensus_claim_hash": consensus_hash,
                "authority": False,
            }
        ),
    }

    return {
        "status": "LIVE" if all_live else "PARTIAL" if completed else "NEXT_PENDING",
        "live": all_live,
        "platform": "Tenki",
        "snapshot_id": TENKI_SNAPSHOT_ID,
        "authority": False,
        "plan": plan,
        "configured_endpoint_count": len(endpoints),
        "workers": results,
        "claim": completed[0].get("claim") if completed else None,
        "aggregate": aggregate,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "reason": None if all_live else (
            f"Tenki replica swarm requires {plan['replica_width']} distinct live /derive endpoints; "
            f"configured={len(endpoints)}, completed={len(completed)}."
        ),
    }
