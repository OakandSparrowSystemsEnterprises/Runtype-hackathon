# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Authority boundary

`Gatekeeper-V2-NPU` remains the sole authority source. `Runtype-hackathon` is integration/demo shell only. The core invariant is fresh bytes -> immutable SHA-256 ArtifactRef -> Agent A authenticated and denied -> same ArtifactRef handed off -> `authority_transfer_from_artifact=false` -> Agent B independently governed by real V2 -> Gatekeeper permit/GREEN/allowed result -> bounded effect -> sealed receipt. Judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.**

The repaired ontology remains V2-owned and is not duplicated here.

## Core Gate 0

Status: **PENDING LIVE LOCAL PROOF**.

Gate 0 is the core authority proof only: V2 source pin, fresh immutable ArtifactRef, Agent A 403, same ArtifactRef handoff, no authority transfer from possession, Agent B 200, real Gatekeeper permit/GREEN/allowed result, sealed artifact hash/receipt, and progressive evidence preserving the already-sealed verdict.

Commit `c64a6b183ecb499da4a784a54b5f7f99cfe86392` corrects `scripts/prove_gate0.py` to this boundary. It also preserves the useful fresh-artifact diagnostic ordering from `9ef8facf7e1875b9e04db1df09165efa8778fa33`: when signed diagnostic credentials are available, the public-edge diagnostic is run against the exact fresh Gate 0 ArtifactRef, but its result is reported as a separate non-blocking edge-proof track.

A fresh Tenki claim, Cotal evidence, the historical public-edge signed-action 502 closure, sponsor integrations, chain verification, idempotency, and the Deterministic Steward implementation are not prerequisites for Core Gate 0. They remain separate supporting, sponsor, or security proof tracks and must not be represented as Gatekeeper authority.

## Deterministic Steward

Status: **IMPLEMENTATION PENDING**.

The Deterministic Steward is settled design and remains unimplemented. Tenki is not the Steward. Cotal is not the Steward. A Tenki worker, Cotal coordinator, sponsor adapter, or evidence aggregator must never be relabeled as the Deterministic Steward. `scripts/prove_gate0.py` now reports this state explicitly and does not require `deterministic_steward.status == LIVE`.

## Tenki

Platform/runtime status: **LIVE VERIFIED**. Fresh per-run binding status: **requires local live verification for the current run**.

Known-good snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`; sandbox/session `01a043be-5240-7bb3-a336-df794b64e56c`; worker port 8080. `POST /derive` succeeded with exact request fields `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. Tenki remains non-authoritative evidence with `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`.

Historical ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` is historical evidence only and must never be replayed for a new artifact.

Dynamic per-run binding is committed in `07a8d9c3cb2ce2b402dbe490232815159d0d0d49`, evidence forwarding in `daf388ee18ee51d5a1ef8b60cdc8094f9ee802c4`, current effect/principal binding in `eff2f1e004ea86b7f3d65c89cee4840c816c9dd8`, regression coverage in `bbbbbc306c7812d207dcc85ef0e23df328e59ab1` and `99bd9736fe4d3c14d2824b5674dc8c97d176d43f`, and judge UI in `130da411c856a35c3581ba089784687f59dc9563`.

## Cotal

Status: **LIVE where already proven**. Preserve its multi-principal identity/handoff role. Cotal coordinates and moves work; it does not grant Gatekeeper authority and it is not the Deterministic Steward.

## Public-edge signed-action 502

Status: **PENDING LIVE CLOSURE** and not a Core Gate 0 blocker.

Missing auth correctly returns `401 missing_agent_auth`. The action edge retains HMAC verification, capability gating, immutable ArtifactRef validation, and the real `action-edge -> GATEKEEPER_BASE_URL -> /api/domains/parent-shield/navigation/evaluate` call-home boundary. `scripts/diagnose_action_edge.py` remains fail-closed for public/action-edge routing and upstream failures. When diagnostic credentials are present, `scripts/prove_gate0.py` now binds that diagnostic to the fresh Gate 0 ArtifactRef and reports `edge_signed_action` independently.

Do not mark this track FIXED until a real signed public-edge request succeeds.

## Sponsor tracks

AIsa.ONE x Mitosis: **PENDING REAL INTEGRATION/PROOF**. Cloudflare: **PENDING REAL INTEGRATION/PROOF**. Nebius: **OPTIONAL / PENDING**. Sponsor development may proceed in isolated feature-flagged paths when independent, but no sponsor may be shown as LIVE until its own real end-to-end result is proven. Sponsor outputs remain non-authoritative evidence or compute inputs and cannot assert authority, permit, capability, token, or Gatekeeper verdict.

## V2 pin

Source pin remains Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. `scripts/verify_v2_source_pin.py` remains fail-closed. Runtime process/image identity remains explicitly unproven by the current V2 health contract.

## Verification and CI

The committed `scripts/prove_gate0.py` blob `94180fedba5a43ba150b2423a16ec32177d9fc9d` was fetched back from the branch after commit `c64a6b183ecb499da4a784a54b5f7f99cfe86392` and inspected for the corrected core Gate 0 boundary, fresh ArtifactRef creation, optional exact-artifact edge diagnostic, and explicit Deterministic Steward `IMPLEMENTATION_PENDING` state.

Existing executable evidence remains the targeted Tenki authority-boundary tests, progressive evidence isolation tests, and nine-case signed-action diagnostic classifier suite. No live localhost proof is claimed from the connector environment.

**CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE.** No no-op CI trigger was created and Gatekeeper-V2-NPU was not modified.

## Next action

Pull branch head and run `python .\scripts\prove_gate0.py` from the active Day 2 shell with `GATEKEEPER_V2_SOURCE_ROOT` set. If the same shell also carries the real agent signing environment, the separate edge 502 diagnostic will run automatically against the fresh artifact without blocking the core authority result.
