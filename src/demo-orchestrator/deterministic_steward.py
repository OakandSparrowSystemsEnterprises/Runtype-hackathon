from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import time

from arena import run_cotal_probe
from tenki_swarm import run_tenki_swarm


CONTRACT = "oasse.deterministic-steward.v1"
MAX_WORKERS = 4


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

    seed = {
        "contract": CONTRACT,
        "artifact_ref": artifact_ref,
        "requested_effect": requested_effect,
        "principal": principal,
        "authority": False,
    }
    plan_id = _digest(seed)
    workers = [
        {
            "worker_id": f"{plan_id}:cotal",
            "role": "authenticated-coordination-and-handoff",
            "plane": "cotal",
            "authority": False,
        },
        {
            "worker_id": f"{plan_id}:tenki-goi",
            "role": "goi-derived-evidence",
            "plane": "tenki",
            "authority": False,
        },
    ]
    return {
        **seed,
        "plan_id": plan_id,
        "workers": workers,
    }


def _run_worker(spec, artifact_ref, requested_effect, principal):
    started = time.perf_counter()
    try:
        if spec["plane"] == "cotal":
            output = run_cotal_probe(artifact_ref)
            live = bool(output.get("ok"))
        elif spec["plane"] == "tenki":
            output = run_tenki_swarm(artifact_ref, requested_effect, principal)
            live = bool(output.get("live")) and output.get("status") == "LIVE"
        else:
            raise RuntimeError(f"unsupported Steward worker plane: {spec['plane']}")
        status = "COMPLETED" if live else "PENDING"
        error = None
    except Exception as exc:
        output = None
        live = False
        status = "FAILED"
        error = f"{type(exc).__name__}: {exc}"

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    semantic_result = {
        "worker_id": spec["worker_id"],
        "role": spec["role"],
        "plane": spec["plane"],
        "status": status,
        "live": live,
        "authority": False,
        "error": error,
        "output": output,
    }
    return {
        **semantic_result,
        "elapsed_ms": elapsed_ms,
        "result_hash": _digest(semantic_result),
    }


def run_deterministic_steward(artifact_ref, requested_effect, principal):
    plan = build_plan(artifact_ref, requested_effect, principal)
    started = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(plan["workers"]))) as pool:
        futures = {
            pool.submit(
                _run_worker,
                spec,
                artifact_ref,
                requested_effect,
                principal,
            ): spec
            for spec in plan["workers"]
        }
        for future in as_completed(futures):
            results.append(future.result())

    # Completion order and worker timing are intentionally excluded from the
    # deterministic state. Both remain visible as provenance.
    results.sort(key=lambda item: item["worker_id"])
    live_workers = sum(1 for item in results if item["live"])
    failed_workers = sum(1 for item in results if item["status"] == "FAILED")
    all_live = live_workers == len(results)

    aggregate_material = {
        "contract": CONTRACT,
        "plan_id": plan["plan_id"],
        "artifact_ref": artifact_ref,
        "requested_effect": requested_effect,
        "principal": principal,
        "authority": False,
        "worker_result_hashes": [item["result_hash"] for item in results],
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
        "live_workers": live_workers,
        "failed_workers": failed_workers,
        "failure_isolated": failed_workers > 0 and live_workers > 0,
        "state_hash": state_hash,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "gatekeeper_authority_required_for_effects": True,
    }
