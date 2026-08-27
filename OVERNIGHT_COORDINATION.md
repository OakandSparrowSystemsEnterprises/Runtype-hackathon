# Hackathon Overnight Coordination

Checkpoint date: 2026-08-26
Branch: `overnight-build-2026-08-26`
Base commit: `9688b0dee0f5e8227267255308aa7ea7df186da7`

## Frozen authority boundary

The certified/private Gatekeeper V2 core is read-only for this overnight pass. The hackathon repository is the integration layer. The central proof remains: raw bytes become an immutable ArtifactRef; Agent A can be authenticated and still receive 403; the same ArtifactRef can be handed to Agent B; artifact possession does not transfer authority; Agent B can be independently authorized; Gatekeeper alone authorizes the effect and produces the sealed receipt.

Cotal coordinates and authenticates its own broker/channel operations but is not Gatekeeper authority. HMAC proves the demo edge signing scheme, not Cotal identity. Deterministic Steward remains implementation pending. Tenki remains not-live until a real worker contributes verified execution to the Arena path. GOI-derived claims are evidence only and cannot authorize effects.

## Verified starting point

Latest repository commits already contain the judge-facing Arena, Cotal swarm probes, five-domain governed estate, chain verification, idempotency proof, Windows null-backed Cotal subprocess handling, parallel Cotal probes, and concurrent Cotal/estate execution. Today’s measured direct Gatekeeper latency was approximately 18 ms minimum, 22.7 ms p50, 24.65 ms mean, 36.45 ms p95, and 48.29 ms maximum. The two-agent artifact/handoff demo measured about 240 ms. The prior full Arena measurement around 13.5 seconds is orchestration/evidence sweep latency and must not be presented as Gatekeeper decision latency.

The Tenki template `gatekeeper-goi-worker-v2` was built successfully earlier today. Snapshot observed in the working session: `07fd77b8-7caf-400e-8e8e-42eb16396098`. This file records that checkpoint only; it does not claim the worker is presently live or reachable.

A public-edge signed-action path also produced a 502 earlier today after unsigned/missing auth correctly returned 401 `missing_agent_auth`. Treat that as a runtime hardening target, not as a resolved condition.

## Workstream state

Progressive judge UX: ACTIVE. Goal is to expose the base authority-transfer verdict first, then resolve sponsor and evidence planes independently.

Cotal sponsor proof: LIVE in the previously verified local runtime. Preserve steward assignment, Agent A handoff, Agent A execution denial, and Agent B execution allowance as distinct facts.

Tenki / GOI: ACTIVE but not live. Build the contract and evidence boundary without fabricating remote execution.

Security evidence: LIVE in the previously verified local runtime. Preserve chain and idempotency semantics while moving them off the critical first-paint path.

Windows/runtime hardening: ACTIVE. Avoid inherited pipe hangs, unnecessary serial subprocess startup, and global failure caused by optional sponsor evidence.

Judge narrative: ACTIVE. Core line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.** Supporting line: **Cotal moves the work. Tenki computes evidence. GOI characterizes bounded state. Gatekeeper alone authorizes the effect.**

## Dependency order

First deployable unit: split the fast authority-transfer result from the supporting Arena evidence request so the judge sees the Gatekeeper outcome before the full evidence sweep completes. Supporting evidence must be derived from the ArtifactRef created by the verified base run, not from stub data.

Second unit: add explicit timing fields that distinguish base authority path from supporting evidence duration and total Arena duration.

Third unit: add a Tenki/GOI evidence adapter contract with a fail-visible not-live state until real worker execution can be verified.

Fourth unit: harden the signed public-edge failure path and improve failure isolation for optional sponsor planes.

Every unit ends with repository-level verification before it is marked complete. Keep unfinished workstreams open until the final dependency is complete or genuinely blocked.

## Overnight progress

Turn 1 established this coordination checkpoint on branch `overnight-build-2026-08-26`. Commit `91ab02e337440b94ab45287337daba3881ccec18` added `src/demo-orchestrator/progressive_evidence.py`, a real supporting-evidence runner that accepts the ArtifactRef from the base authority proof and resolves Cotal, the five-domain governed estate, and the existing security bundle without giving the ArtifactRef any authority semantics. Cotal and estate execute in parallel with the security bundle; chain verification and idempotency retain their established internal order. The runner emits a measured `supporting_evidence_ms` scoped explicitly to `cotal_plus_estate_plus_security`.

Verification for the new module: Python syntax compilation passed. Runtime sponsor verification is intentionally not claimed because the local Cotal/Tenki/Gatekeeper services are not reachable from this automation environment. The next dependency-safe unit is to expose this runner through a separate evidence endpoint while preserving `/api/demo/run` as the fast authority-transfer path, then switch the Arena UI to render the base result before requesting supporting evidence.
