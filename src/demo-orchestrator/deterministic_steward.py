from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time

from arena import run_cotal_probe
from tenki_swarm import build_swarm_plan, run_tenki_swarm


CONTRACT = "oasse.deterministic-steward.v2"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def build_plan(artifact_ref, requested_effect, principal):
    if not isinstance(artifact_ref, str) or not artifact_ref.startswith("sha256:"):
        raise RuntimeError("Deterministic Steward requires a canonical ArtifactRef")
    if not isinstance(requested_effect, str) or not requested_effect:
        raise RuntimeError("Deterministic Steward requires requested_effect")
    if not isinstance(principal, str) or not principal:
        raise RuntimeError("Deterministic Steward requires principal")

    tenki_plan = build_swarm_plan(artifact_ref, requested_effect, principal)
    seed = {
        "contract": CONTRACT,
        "artifact_ref": artifact_ref,
        "requested_effect": requested_effect,
        "principal": principal,
        "tenki_replica_width": tenki_plan["replica_width"],
        "authority": False,
    }
    plan_id = _digest(seed)
    workers = [
        {
            "worker_id": f"{plan_id}:cotal-coordination",
            "role": "authenticated-coordination-and-handoff",
            "plane": "cotal",
            "authority": False,
        }
    ]
    workers.extend(
        {
            "worker_id": f"{plan_id}:tenki-replica-{item['replica_index']:02d}",
            "role": "independent-goi-derived-claim-replica",
            "plane": "tenki",
            "replica_index": item["replica_index"],
            "authority": False,
        }
        for item in tenki_plan["workers"]
    )
    return {
        **seed,
        "plan_id": plan_id,
        "workers": workers,
        "tenki_plan_id": tenki_plan["plan_id"],
    }


def _cotal_result(plan_id, artifact_ref):
    started = time.perf_counter()
    try:
        output = run_cotal_probe(artifact_ref)
        live = bool(output.get("ok"))
        status = "COMPLETED" if live else "PENDING"
        error = None
    except Exception as exc:
        output = None
        live = False
        status = "FAILED"
        error = f"{type(exc).__name__}: {exc}"

    semantic = {
        "worker_id": f"{plan_id}:cotal-coordination",
        "role": "authenticated-coordination-and-handoff",
        "plane": "cotal",
        "status": status,
        "live": live,
        "authority": False,
        "error": error,
        "output": output,
    }
    return {
        **semantic,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "result_hash": _digest(semantic),
    }


def _tenki_worker_result(plan_id, replica):
    semantic = {
        "worker_id": f"{plan_id}:tenki-replica-{replica['replica_index']:02d}",
        "role": "independent-goi-derived-claim-replica",
        "plane": "tenki",
        "replica_index": replica["replica_index"],
        "status": replica["status"],
        "live": bool(replica.get("live")),
        "authority": False,
        "claim_hash": replica.get("claim_hash"),
        "error": replica.get("error"),
    }
    return {
        **semantic,
        "elapsed_ms": replica.get("elapsed_ms"),
        "claim": replica.get("claim"),
        "result_hash": _digest(semantic),
    }


def run_deterministic_steward(artifact_ref, requested_effect, principal):
    plan = build_plan(artifact_ref, requested_effect, principal)
    started = time.perf_counter()

    # Coordination and Tenki compute are independent once the governed
    # ArtifactRef exists. The Steward overlaps them, then deterministically
    # aggregates the worker records after both planes resolve.
    with ThreadPoolExecutor(max_workers=2) as pool:
        cotal_future = pool.submit(_cotal_result, plan["plan_id"], artifact_ref)
        tenki_future = pool.submit(
            run_tenki_swarm,
            artifact_ref,
            requested_effect,
            principal,
        )
        cotal = cotal_future.result()
        tenki_swarm = tenki_future.result()

    results = [cotal]
    results.extend(
        _tenki_worker_result(plan["plan_id"], replica)
        for replica in tenki_swarm.get("workers", [])
    )
    results.sort(key=lambda item: item["worker_id"])

    live_workers = sum(1 for item in results if item["live"])
    failed_workers = sum(1 for item in results if item["status"] == "FAILED")
    pending_workers = sum(1 for item in results if item["status"] == "PENDING")
    all_live = (
        len(results) == len(plan["workers"])
        and live_workers == len(plan["workers"])
        and tenki_swarm.get("live") is True
        and tenki_swarm.get("aggregate", {}).get("consensus") is True
    )

    aggregate_material = {
        "contract": CONTRACT,
        "plan_id": plan["plan_id"],
        "artifact_ref": artifact_ref,
        "requested_effect": requested_effect,
        "principal": principal,
        "authority": False,
        "worker_result_hashes": [item["result_hash"] for item in results],
        "tenki_consensus_claim_hash": tenki_swarm.get("aggregate", {}).get(
            "consensus_claim_hash"
        ),
    }
    state_hash = _digest(aggregate_material)

    return {
        "status": "LIVE" if all_live else "PARTIAL" if live_workers else "PENDING",
        "implemented": True,
        "swarm_native": True,
        "authority": False,
        "contract": CONTRACT,
        "plan": plan,
        "workers": results,
        "worker_count": len(results),
        "planned_worker_count": len(plan["workers"]),
        "live_workers": live_workers,
        "failed_workers": failed_workers,
        "pending_workers": pending_workers,
        "failure_isolated": failed_workers > 0 and live_workers > 0,
        "tenki_swarm": tenki_swarm,
        "tenki_consensus": tenki_swarm.get("aggregate", {}).get("consensus", False),
        "state_hash": state_hash,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "gatekeeper_authority_required_for_effects": True,
    }
