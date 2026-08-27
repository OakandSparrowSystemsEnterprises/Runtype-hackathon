from concurrent.futures import ThreadPoolExecutor
import time

from aisa_mitosis import run_aisa_mitosis
from arena import run_arena
from tenki_swarm import run_tenki_swarm


def _failed_plane(name, exc):
    return {
        "ok": False,
        "status": "FAILED",
        "authority": False,
        "error": f"{name}: {type(exc).__name__}: {exc}",
    }


def _steward_pending():
    return {
        "ok": True,
        "status": "IMPLEMENTATION_PENDING",
        "implemented": False,
        "authority": False,
        "role": "settled_design_only",
    }


def run_progressive_evidence(base_demo):
    """Resolve slower evidence planes after the Gatekeeper verdict is already known.

    The current run identity is bound directly into Tenki. Tenki remains derived,
    non-authoritative evidence. The Deterministic Steward is deliberately not a
    runtime dependency and remains implementation-pending.
    """
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
    with ThreadPoolExecutor(max_workers=3) as pool:
        existing_future = pool.submit(run_arena, base_demo)
        tenki_future = pool.submit(
            run_tenki_swarm,
            artifact_ref,
            requested_effect,
            principal,
        )
        sponsor_future = pool.submit(
            run_aisa_mitosis,
            artifact_ref,
            requested_effect,
            principal,
            base_demo.get("target_url"),
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
            tenki = tenki_future.result()
        except Exception as exc:
            tenki = _failed_plane("tenki", exc)
            tenki.update({"live": False, "authority": False})

        try:
            aisa_mitosis = sponsor_future.result()
        except Exception as exc:
            aisa_mitosis = _failed_plane("aisa_mitosis", exc)
            aisa_mitosis.update({
                "implemented": True,
                "sponsor": "AIsa.ONE x Mitosis",
                "live": False,
            })

    elapsed_ms = (time.perf_counter() - started) * 1000
    cotal = existing.get("cotal") or {"ok": False, "status": "UNAVAILABLE"}
    estate = existing.get("estate") or {"ok": False, "status": "UNAVAILABLE"}
    steward = _steward_pending()

    tenki_live = (
        bool(tenki.get("live"))
        and tenki.get("status") == "LIVE"
        and tenki.get("authority") is False
    )
    evidence_complete = (
        bool(cotal.get("ok"))
        and bool(estate.get("ok"))
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
        "sponsor": {"aisa_mitosis": aisa_mitosis},
        "sponsor_evidence_live": aisa_mitosis.get("status") == "LIVE",
    }
