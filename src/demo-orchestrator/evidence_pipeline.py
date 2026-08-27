from concurrent.futures import ThreadPoolExecutor
import time

from arena import run_arena
from tenki_swarm import run_tenki_swarm


def _failed_plane(name, exc):
    return {
        "ok": False,
        "status": "FAILED",
        "authority": False,
        "error": f"{name}: {type(exc).__name__}: {exc}",
    }


def run_progressive_evidence(base_demo):
    """Resolve slower evidence planes after the Gatekeeper verdict is already known.

    Supporting evidence is deliberately failure-isolated. A Cotal/estate failure or a
    Tenki runtime failure must not erase an already-sealed Gatekeeper verdict, and one
    evidence plane must not suppress the result of another.
    """
    artifact_ref = base_demo.get("artifact_ref")
    if not artifact_ref:
        raise RuntimeError("base demo did not return an artifact_ref")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        existing_future = pool.submit(run_arena, base_demo)
        tenki_future = pool.submit(run_tenki_swarm, artifact_ref)

        try:
            existing = existing_future.result()
        except Exception as exc:
            existing = {
                "ok": False,
                "cotal": _failed_plane("cotal_or_estate", exc),
                "estate": _failed_plane("cotal_or_estate", exc),
            }

        try:
            tenki = tenki_future.result()
        except Exception as exc:
            tenki = _failed_plane("tenki", exc)
            tenki.update({
                "live": False,
                "snapshot_id": "07fd77b8-7caf-400e-8e8e-42eb16396098",
                "reason": "Tenki supporting evidence failed; Gatekeeper verdict remains authoritative.",
            })

    elapsed_ms = (time.perf_counter() - started) * 1000
    cotal = existing.get("cotal") or {"ok": False, "status": "UNAVAILABLE"}
    estate = existing.get("estate") or {"ok": False, "status": "UNAVAILABLE"}
    tenki_live = bool(tenki.get("live")) and tenki.get("status") == "LIVE" and tenki.get("authority") is False
    evidence_complete = bool(cotal.get("ok")) and bool(estate.get("ok")) and tenki.get("authority") is False

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
        "deterministic_steward": {
            "status": "LIVE" if tenki_live else "IMPLEMENTATION_PENDING",
            "swarm_native": True,
            "authority": False,
            "compute_substrate": "Tenki",
        },
    }
