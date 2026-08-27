from concurrent.futures import ThreadPoolExecutor
import time

from arena import run_arena
from deterministic_steward import run_deterministic_steward


def _failed_plane(name, exc):
    return {
        "ok": False,
        "status": "FAILED",
        "authority": False,
        "error": f"{name}: {type(exc).__name__}: {exc}",
    }


def run_progressive_evidence(base_demo):
    """Resolve slower evidence planes after the Gatekeeper verdict is already known."""
    artifact_ref = base_demo.get("artifact_ref")
    requested_effect = base_demo.get("requested_effect")
    principal = base_demo.get("effect_principal")

    if not artifact_ref:
        raise RuntimeError("base demo did not return an artifact_ref")
    if not requested_effect:
        raise RuntimeError("base demo did not return requested_effect")
    if not principal:
        raise RuntimeError("base demo did not return effect_principal")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        existing_future = pool.submit(run_arena, base_demo)
        steward_future = pool.submit(
            run_deterministic_steward,
            artifact_ref,
            requested_effect,
            principal,
        )

        try:
            existing = existing_future.result()
        except Exception as exc:
            existing = {
                "ok": False,
                "cotal": _failed_plane("cotal_or_estate", exc),
                "estate": _failed_plane("cotal_or_estate", exc),
            }

        try:
            steward = steward_future.result()
        except Exception as exc:
            steward = _failed_plane("deterministic_steward", exc)
            steward.update({
                "implemented": True,
                "swarm_native": True,
                "authority": False,
                "workers": [],
            })

    elapsed_ms = (time.perf_counter() - started) * 1000
    cotal = existing.get("cotal") or {"ok": False, "status": "UNAVAILABLE"}
    estate = existing.get("estate") or {"ok": False, "status": "UNAVAILABLE"}

    tenki = {"status": "PENDING", "live": False, "authority": False}
    for worker in steward.get("workers") or []:
        if worker.get("plane") == "tenki":
            candidate = worker.get("output")
            if isinstance(candidate, dict):
                tenki = candidate
            break

    steward_live = (
        steward.get("status") == "LIVE"
        and steward.get("implemented") is True
        and steward.get("authority") is False
    )
    tenki_live = (
        bool(tenki.get("live"))
        and tenki.get("status") == "LIVE"
        and tenki.get("authority") is False
    )
    evidence_complete = (
        bool(cotal.get("ok"))
        and bool(estate.get("ok"))
        and steward_live
        and tenki_live
    )

    return {
        "ok": True,
        "phase": "supporting_evidence",
        "authority_source": "Gatekeeper",
        "gatekeeper_verdict_preserved": True,
        "evidence_complete": evidence_complete,
        "supporting_evidence_ms": round(elapsed_ms, 2),
        "base_demo": base_demo,
        "cotal": cotal,
        "estate": estate,
        "tenki": tenki,
        "deterministic_steward": steward,
    }
