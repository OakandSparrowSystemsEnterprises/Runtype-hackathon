from concurrent.futures import ThreadPoolExecutor
import time

import arena
from security_probes import run_chain_verification_probe, run_idempotency_probe


def _run_security_bundle():
    """Run authoritative security probes in their established order.

    Chain verification remains ahead of the idempotency replay probe, matching
    the existing Arena semantics. The pair can execute in parallel with the
    independent Cotal and governed-estate work, but not with each other.
    """
    chain_verification = run_chain_verification_probe()
    idempotency = run_idempotency_probe()
    return {
        "chain_verification": chain_verification,
        "idempotency": idempotency,
        "ok": bool(chain_verification.get("ok")) and bool(idempotency.get("ok")),
    }


def run_supporting_evidence(artifact_ref):
    """Resolve slow supporting evidence after the base authority proof.

    The ArtifactRef is evidence of the already-created work item. It is passed
    into the Cotal coordination probe only. Neither possession of the ref nor
    any result returned here grants Gatekeeper execution authority.
    """
    if not isinstance(artifact_ref, str) or not artifact_ref.strip():
        raise ValueError("artifact_ref must be a non-empty string")

    started = time.perf_counter()

    # Once the base ArtifactRef exists these workstreams are independent.
    # Parallelizing them keeps the judge-facing authority decision off this
    # slower evidence path while preserving the semantics of each probe.
    with ThreadPoolExecutor(max_workers=3) as pool:
        cotal_future = pool.submit(arena.run_cotal_probe, artifact_ref)
        estate_future = pool.submit(arena.run_estate)
        security_future = pool.submit(_run_security_bundle)

        cotal = cotal_future.result()
        estate = estate_future.result()
        security = security_future.result()

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    return {
        "ok": bool(cotal.get("ok")) and bool(estate.get("ok")) and bool(security.get("ok")),
        "artifact_ref": artifact_ref,
        "thesis": "Supporting evidence can resolve after authority without changing authority.",
        "cotal": cotal,
        "estate": estate,
        "security": {
            "chain_verification": security["chain_verification"],
            "idempotency": security["idempotency"],
        },
        "timing": {
            "supporting_evidence_ms": elapsed_ms,
            "scope": "cotal_plus_estate_plus_security",
        },
    }
