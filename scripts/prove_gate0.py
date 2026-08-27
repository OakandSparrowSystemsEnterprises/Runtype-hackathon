#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_URL = os.environ.get("DEMO_ORCHESTRATOR_URL", "http://127.0.0.1:8083").rstrip("/")
TIMEOUT = float(os.environ.get("GATE0_TIMEOUT_SECONDS", "30"))
EXPECTED_EFFECT = os.environ.get("GATE0_EXPECTED_EFFECT", "parent-shield.navigation")
EXPECTED_PRINCIPAL = os.environ.get("GATE0_EXPECTED_PRINCIPAL", "agent-b")


def emit(stage, status, **detail):
    print(json.dumps({"stage": stage, "status": status, **detail}, separators=(",", ":")))


def run_checked(script, required_marker=None):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = proc.stdout.strip()
    if output:
        print(output)
    if proc.returncode != 0:
        return False
    if required_marker is not None and required_marker not in output:
        return False
    return True


def post_json(path, payload):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        ORCHESTRATOR_URL + path,
        data=raw,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body[:1000]}
        return exc.code, parsed


def require(condition, stage, reason, **detail):
    if condition:
        emit(stage, "PASS", **detail)
        return
    emit(stage, "FAIL", reason=reason, **detail)
    raise RuntimeError(f"{stage}: {reason}")


def main():
    require(
        bool(os.environ.get("GATEKEEPER_V2_SOURCE_ROOT")),
        "v2_source_pin_precondition",
        "GATEKEEPER_V2_SOURCE_ROOT must point at the source-of-truth V2 checkout",
    )

    require(
        run_checked("verify_v2_source_pin.py", '"status":"PASS"'),
        "v2_source_pin",
        "V2 source pin did not verify",
    )

    required_diag = ("DIAGNOSTIC_AGENT_ID", "DIAGNOSTIC_AGENT_SECRET", "DIAGNOSTIC_ARTIFACT_REF")
    missing_diag = [name for name in required_diag if not os.environ.get(name)]
    require(
        not missing_diag,
        "signed_action_precondition",
        "real signed diagnostic credentials and existing ArtifactRef are required",
        missing=missing_diag,
    )

    require(
        run_checked("diagnose_action_edge.py", '"status":"SIGNED_PROBE_COMPLETED"'),
        "signed_action_502",
        "signed-action diagnostic did not complete cleanly; Gate 0 cannot pass",
    )

    verdict_status, verdict = post_json(
        "/api/demo/run",
        {"mode": "verdict", "intent": "Gate 0 fresh authority-transfer proof"},
    )
    require(verdict_status == 200 and verdict.get("ok") is True, "fresh_core_proof", "fresh demo run failed", http_status=verdict_status)

    artifact_ref = verdict.get("artifact_ref")
    require(
        isinstance(artifact_ref, str) and artifact_ref.startswith("sha256:") and len(artifact_ref) == 71,
        "artifact_ref",
        "fresh run did not return a valid immutable ArtifactRef",
        artifact_ref=artifact_ref,
    )

    require(
        verdict.get("agent_a", {}).get("status") == 403
        and verdict.get("agent_b", {}).get("status") == 200
        and verdict.get("authority_transfer_from_artifact") is False,
        "authority_transfer_invariant",
        "A deny -> handoff -> B independently governed invariant failed",
    )

    gatekeeper = verdict.get("gatekeeper") or {}
    gatekeeper_artifact = gatekeeper.get("artifact") or {}
    require(
        gatekeeper.get("execution") == "allowed" or gatekeeper.get("formal") == "permit",
        "gatekeeper_verdict",
        "Gatekeeper did not produce an allowed/permit verdict",
        formal=gatekeeper.get("formal"),
        execution=gatekeeper.get("execution"),
    )
    require(
        bool(gatekeeper_artifact.get("artifact_hash")),
        "sealed_receipt",
        "Gatekeeper result did not include a sealed artifact hash",
        artifact_hash=gatekeeper_artifact.get("artifact_hash"),
    )

    evidence_status, evidence = post_json("/api/demo/evidence", {"run_id": verdict.get("run_id")})
    require(evidence_status == 200 and evidence.get("ok") is True, "progressive_evidence", "progressive evidence request failed", http_status=evidence_status)
    require(evidence.get("gatekeeper_verdict_preserved") is True, "verdict_preservation", "supporting evidence did not preserve the sealed Gatekeeper verdict")

    tenki = evidence.get("tenki") or {}
    claim = tenki.get("claim") or {}
    require(
        tenki.get("live") is True and tenki.get("status") == "LIVE" and tenki.get("authority") is False,
        "tenki_live",
        "fresh Tenki evidence did not resolve LIVE and non-authoritative",
        tenki_status=tenki.get("status"),
    )
    require(
        claim.get("artifact_ref") == artifact_ref
        and claim.get("artifact_sha256") == artifact_ref.split(":", 1)[1]
        and claim.get("requested_effect") == EXPECTED_EFFECT
        and claim.get("principal") == EXPECTED_PRINCIPAL
        and claim.get("authority") is False
        and claim.get("compute_plane") == "tenki"
        and claim.get("role") == "derived_claim_only",
        "tenki_claim_binding",
        "Tenki claim is not bound to the exact fresh governed artifact/effect/principal",
        claim_artifact_ref=claim.get("artifact_ref"),
        requested_effect=claim.get("requested_effect"),
        principal=claim.get("principal"),
    )

    steward = evidence.get("deterministic_steward") or {}
    require(
        steward.get("status") == "LIVE" and steward.get("authority") is False,
        "steward_evidence",
        "Deterministic Steward did not resolve as live non-authoritative compute",
        steward_status=steward.get("status"),
    )

    emit(
        "GATE_0",
        "PASS",
        artifact_ref=artifact_ref,
        gatekeeper_receipt=gatekeeper_artifact.get("artifact_hash"),
        gatekeeper_v2_hop_ms=(verdict.get("latency") or {}).get("gatekeeper_v2_hop_ms"),
        authority_transfer_proof_ms=(verdict.get("latency") or {}).get("authority_transfer_proof_ms"),
        tenki_elapsed_ms=tenki.get("elapsed_ms"),
        tenki_claim_hash=claim.get("claim_hash"),
        next_sponsor_eligible="AISA.ONE x MITOSIS",
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        emit("GATE_0", "FAIL", reason=str(exc), next_sponsor_eligible=None)
        sys.exit(1)
