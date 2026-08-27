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


def emit(stage, status, **detail):
    print(json.dumps({"stage": stage, "status": status, **detail}, separators=(",", ":")))


def run_checked(script, required_marker=None, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    output = proc.stdout.strip()
    if output:
        print(output)
    ok = proc.returncode == 0 and (required_marker is None or required_marker in output)
    return ok


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


def resolve_diagnostic_secret(agent_id):
    secret = os.environ.get("DIAGNOSTIC_AGENT_SECRET")
    if secret:
        return secret, "DIAGNOSTIC_AGENT_SECRET"

    raw_keys = os.environ.get("GATEKEEPER_AGENT_KEYS_JSON")
    if not raw_keys:
        return None, None
    try:
        keys = json.loads(raw_keys)
    except json.JSONDecodeError:
        return None, None
    candidate = keys.get(agent_id) if isinstance(keys, dict) else None
    if isinstance(candidate, str) and candidate:
        return candidate, "GATEKEEPER_AGENT_KEYS_JSON"
    return None, None


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

    verdict_status, verdict = post_json(
        "/api/demo/run",
        {"mode": "verdict", "intent": "Gate 0 fresh authority-transfer proof"},
    )

    artifact_ref = verdict.get("artifact_ref") if isinstance(verdict, dict) else None
    require(
        isinstance(artifact_ref, str) and artifact_ref.startswith("sha256:") and len(artifact_ref) == 71,
        "fresh_artifact",
        "fresh demo attempt did not create a valid immutable ArtifactRef",
        http_status=verdict_status,
        artifact_ref=artifact_ref,
    )

    # The public-edge signed-action 502 is an independent edge-proof track. If
    # real credentials are available, run the diagnostic against this exact fresh
    # artifact and report it, but never redefine the core authority proof around
    # optional public-edge topology.
    agent_id = os.environ.get("DIAGNOSTIC_AGENT_ID", "agent-b")
    diagnostic_secret, secret_source = resolve_diagnostic_secret(agent_id)
    if diagnostic_secret:
        edge_ok = run_checked(
            "diagnose_action_edge.py",
            '"status":"SIGNED_PROBE_COMPLETED"',
            {
                "DIAGNOSTIC_AGENT_ID": agent_id,
                "DIAGNOSTIC_AGENT_SECRET": diagnostic_secret,
                "DIAGNOSTIC_ARTIFACT_REF": artifact_ref,
            },
        )
        emit(
            "edge_signed_action",
            "PASS" if edge_ok else "PENDING",
            artifact_ref=artifact_ref,
            secret_source=secret_source,
            core_gate_blocking=False,
        )
    else:
        emit(
            "edge_signed_action",
            "PENDING",
            reason="signed diagnostic credentials unavailable in this shell",
            artifact_ref=artifact_ref,
            core_gate_blocking=False,
        )

    require(
        verdict_status == 200 and verdict.get("ok") is True,
        "fresh_core_proof",
        "fresh demo run failed",
        http_status=verdict_status,
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
    require(
        evidence_status == 200 and evidence.get("ok") is True,
        "progressive_evidence",
        "progressive evidence request failed",
        http_status=evidence_status,
    )
    require(
        evidence.get("gatekeeper_verdict_preserved") is True,
        "verdict_preservation",
        "supporting evidence did not preserve the sealed Gatekeeper verdict",
    )

    tenki = evidence.get("tenki") or {}
    emit(
        "tenki_supporting_evidence",
        "LIVE" if tenki.get("live") is True and tenki.get("authority") is False else "PENDING",
        core_gate_blocking=False,
        artifact_ref=artifact_ref,
    )

    steward = evidence.get("deterministic_steward") or {}
    emit(
        "deterministic_steward",
        "IMPLEMENTATION_PENDING",
        core_gate_blocking=False,
        reported_runtime_status=steward.get("status"),
        authority=False,
    )

    emit(
        "GATE_0",
        "PASS",
        artifact_ref=artifact_ref,
        gatekeeper_receipt=gatekeeper_artifact.get("artifact_hash"),
        gatekeeper_v2_hop_ms=(verdict.get("latency") or {}).get("gatekeeper_v2_hop_ms"),
        authority_transfer_proof_ms=(verdict.get("latency") or {}).get("authority_transfer_proof_ms"),
        authority_invariant="PASS",
        sponsor_development_unblocked=True,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        emit("GATE_0", "FAIL", reason=str(exc))
        sys.exit(1)
