from concurrent.futures import ThreadPoolExecutor
import time

from arena import run_arena
from tenki_swarm import run_tenki_swarm


def run_progressive_evidence(base_demo):
    """Resolve slower evidence planes after the Gatekeeper verdict is already known."""
    artifact_ref = base_demo.get("artifact_ref")
    if not artifact_ref:
        raise RuntimeError("base demo did not return an artifact_ref")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        existing_future = pool.submit(run_arena, base_demo)
        tenki_future = pool.submit(run_tenki_swarm, artifact_ref)
        existing = existing_future.result()
        tenki = tenki_future.result()

    elapsed_ms = (time.perf_counter() - started) * 1000
    tenki_live = bool(tenki.get("live"))

    return {
        "ok": bool(existing.get("ok")) and (tenki.get("authority") is False),
        "phase": "supporting_evidence",
        "authority_source": "Gatekeeper",
        "supporting_evidence_ms": round(elapsed_ms, 2),
        "base_demo": base_demo,
        "cotal": existing.get("cotal"),
        "estate": existing.get("estate"),
        "tenki": tenki,
        "deterministic_steward": {
            "status": "LIVE" if tenki_live else "IMPLEMENTATION_PENDING",
            "swarm_native": True,
            "authority": False,
            "compute_substrate": "Tenki",
        },
    }
