from concurrent.futures import ThreadPoolExecutor
import time

from arena import run_arena
from deterministic_steward import run_deterministic_steward
from sponsor_aisa_mitosis import run_aisa_mitosis_evidence
from security_probes import run_chain_verification_probe, run_idempotency_probe


def _failed_plane(name, exc):
    return {
        "ok": False,
        "status": "FAILED",
        "authority": False,
        "error": f"{name}: {type(exc).__name__}: {exc}",
    }


def run_aisa_mitosis(artifact_ref, requested_effect, principal, target_url=None):
    """Run the proven AIsa Exa -> Mitosis Cortex evidence route for this demo run.

    The sponsor plane remains non-authoritative. Gatekeeper has already sealed the
    verdict before this function is called; this function only enriches and stores
    supporting evidence.
    """
    target = target_url or "unspecified target"
    query = (
        "current public evidence relevant to pre-execution AI governance for "
        f"target={target}; requested_effect={requested_effect}; principal={principal}"
    )
    result = run_aisa_mitosis_evidence(query=query)
    if not isinstance(result, dict):
        raise RuntimeError("AIsa x Mitosis sponsor adapter returned a non-object result")

    # Bind the supporting evidence record to the current governed run using only
    # locally supplied identifiers. Sponsor output still cannot grant authority.
    result.setdefault("implemented", True)
    result.setdefault("sponsor", "AIsa.ONE x Mitosis")
    result["authority"] = False
    result["artifact_ref"] = artifact_ref
    result["requested_effect"] = requested_effect
    result["principal"] = principal
    result["target_url"] = target_url
    return result


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
    with ThreadPoolExecutor(max_workers=3) as pool:
        existing_future = pool.submit(run_arena, base_demo)
        steward_future = pool.submit(
            run_deterministic_steward,
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
            steward = steward_future.result()
        except Exception as exc:
            steward = _failed_plane("deterministic_steward", exc)
            steward.update({
                "implemented": True,
                "swarm_native": True,
                "authority": False,
                "workers": [],
            })

        try:
            aisa_mitosis = sponsor_future.result()
        except Exception as exc:
            aisa_mitosis = _failed_plane("aisa_mitosis", exc)
            aisa_mitosis.update({
                "implemented": True,
                "sponsor": "AIsa.ONE x Mitosis",
                "live": False,
            })

    # Security verification belongs to the slower evidence phase. It executes
    # only after the base Gatekeeper verdict is already cached and sealed, so
    # these checks can never delay or alter the authority decision shown first.
    try:
        chain_verification = run_chain_verification_probe()
    except Exception as exc:
        chain_verification = _failed_plane("chain_verification", exc)

    try:
        idempotency = run_idempotency_probe()
    except Exception as exc:
        idempotency = _failed_plane("idempotency", exc)

    elapsed_ms = (time.perf_counter() - started) * 1000
    cotal = existing.get("cotal") or {"ok": False, "status": "UNAVAILABLE"}
    estate = existing.get("estate") or {"ok": False, "status": "UNAVAILABLE"}

    tenki = steward.get("tenki_swarm") or {
        "status": "PENDING",
        "live": False,
        "authority": False,
    }

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
    security_ok = bool(chain_verification.get("ok")) and bool(idempotency.get("ok"))
    evidence_complete = (
        bool(cotal.get("ok"))
        and bool(estate.get("ok"))
        and steward_live
        and tenki_live
        and security_ok
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
        "security": {
            "chain_verification": chain_verification,
            "idempotency": idempotency,
        },
        "tenki": tenki,
        "deterministic_steward": steward,
        "sponsor": {"aisa_mitosis": aisa_mitosis},
        "sponsor_evidence_live": aisa_mitosis.get("status") == "LIVE",
    }
