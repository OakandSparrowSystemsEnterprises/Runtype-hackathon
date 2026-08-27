#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

ORCHESTRATOR_URL = os.environ.get("DEMO_ORCHESTRATOR_URL", "http://127.0.0.1:8083").rstrip("/")
TIMEOUT = float(os.environ.get("STEWARD_PROOF_TIMEOUT_SECONDS", "60"))


def emit(stage, status, **detail):
    print(json.dumps({"stage": stage, "status": status, **detail}, separators=(",", ":")))


def post(path, payload):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        ORCHESTRATOR_URL + path,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            body = {"raw": raw_body}
        return exc.code, body


def require(condition, stage, reason, **detail):
    if condition:
        emit(stage, "PASS", **detail)
        return
    emit(stage, "FAIL", reason=reason, **detail)
    raise RuntimeError(f"{stage}: {reason}")


def configured_tenki_endpoints():
    raw_many = os.environ.get("TENKI_DERIVE_URLS", "")
    endpoints = [item.strip() for item in raw_many.split(",") if item.strip()]
    if endpoints:
        return endpoints
    single = os.environ.get("TENKI_DERIVE_URL", "").strip()
    return [single] if single else []


def main():
    verdict_status, verdict = post(
        "/api/demo/run",
        {"mode": "verdict", "intent": "Deterministic Steward live swarm proof"},
    )
    require(
        verdict_status == 200 and verdict.get("ok") is True,
        "fresh_governed_verdict",
        "fresh Gatekeeper authority proof failed before Steward execution",
        http_status=verdict_status,
    )

    artifact_ref = verdict.get("artifact_ref")
    run_id = verdict.get("run_id")
    emit("artifact_ref", "PASS", artifact_ref=artifact_ref, run_id=run_id)

    evidence_status, evidence = post("/api/demo/evidence", {"run_id": run_id})
    require(
        evidence_status == 200 and evidence.get("ok") is True,
        "progressive_evidence",
        "supporting evidence phase failed",
        http_status=evidence_status,
    )

    steward = evidence.get("deterministic_steward") or {}
    workers = steward.get("workers") or []
    tenki_swarm = steward.get("tenki_swarm") or {}
    tenki_aggregate = tenki_swarm.get("aggregate") or {}

    require(
        steward.get("implemented") is True
        and steward.get("swarm_native") is True
        and steward.get("authority") is False,
        "steward_contract",
        "Deterministic Steward contract not active",
        steward_status=steward.get("status"),
    )
    require(
        bool(steward.get("plan", {}).get("plan_id"))
        and bool(steward.get("state_hash"))
        and len(workers) >= 3,
        "deterministic_state",
        "Steward did not produce a deterministic multi-worker state",
        worker_count=len(workers),
        planned_worker_count=steward.get("planned_worker_count"),
    )
    require(
        all(worker.get("authority") is False for worker in workers),
        "worker_authority_boundary",
        "a Steward worker attempted to carry authority",
    )

    cotal_workers = [worker for worker in workers if worker.get("plane") == "cotal"]
    tenki_workers = [worker for worker in workers if worker.get("plane") == "tenki"]
    require(
        len(cotal_workers) == 1 and cotal_workers[0].get("live") is True,
        "cotal_coordination_worker",
        "Cotal coordination worker is not live",
        worker_status=cotal_workers[0].get("status") if cotal_workers else None,
    )
    require(
        len(tenki_workers) >= 2,
        "tenki_swarm_plan",
        "Steward did not schedule a real multi-replica Tenki swarm",
        tenki_worker_count=len(tenki_workers),
    )

    endpoints = configured_tenki_endpoints()
    required_width = int(tenki_swarm.get("plan", {}).get("replica_width") or len(tenki_workers))
    if len(endpoints) >= required_width:
        require(
            tenki_swarm.get("live") is True
            and tenki_aggregate.get("consensus") is True
            and tenki_aggregate.get("completed") == required_width,
            "tenki_replica_consensus",
            "configured Tenki replica swarm did not complete deterministic consensus",
            configured_endpoints=len(endpoints),
            replica_width=required_width,
            completed=tenki_aggregate.get("completed"),
            failed=tenki_aggregate.get("failed"),
            pending=tenki_aggregate.get("pending"),
            consensus=tenki_aggregate.get("consensus"),
        )
    else:
        emit(
            "tenki_replica_consensus",
            "PENDING",
            configured_endpoints=len(endpoints),
            replica_width=required_width,
            completed=tenki_aggregate.get("completed"),
            failed=tenki_aggregate.get("failed"),
            pending=tenki_aggregate.get("pending"),
            reason="distinct live Tenki /derive endpoints are required for every replica",
            core_steward_implementation_blocking=False,
        )

    final_live = steward.get("status") == "LIVE"
    emit(
        "DETERMINISTIC_STEWARD",
        "PASS" if final_live else "PARTIAL",
        implemented=True,
        swarm_native=True,
        authority=False,
        artifact_ref=artifact_ref,
        plan_id=steward.get("plan", {}).get("plan_id"),
        state_hash=steward.get("state_hash"),
        worker_count=steward.get("worker_count"),
        live_workers=steward.get("live_workers"),
        failed_workers=steward.get("failed_workers"),
        pending_workers=steward.get("pending_workers"),
        tenki_replica_width=required_width,
        tenki_consensus=steward.get("tenki_consensus"),
    )
    return 0 if (final_live or len(endpoints) < required_width) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        emit("DETERMINISTIC_STEWARD", "FAIL", reason=str(exc))
        sys.exit(1)
