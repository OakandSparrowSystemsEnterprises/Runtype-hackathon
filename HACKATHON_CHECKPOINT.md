# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Authority boundary

`Gatekeeper-V2-NPU` remains the sole authority source. `Runtype-hackathon` is integration/demo shell only. The core invariant is fresh bytes -> immutable SHA-256 ArtifactRef -> Agent A authenticated and denied -> same ArtifactRef handed off -> `authority_transfer_from_artifact=false` -> Agent B independently governed by real V2 -> Gatekeeper permit/GREEN/allowed result -> bounded effect -> sealed receipt. Judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.**

The repaired ontology remains V2-owned and is not duplicated here.

## Core Gate 0

Status: **PASS — LIVE LOCAL PROOF VERIFIED 2026-08-27**.

Live proof ArtifactRef: `sha256:810908125d05ea8eb04edf3607ed0c070f10c04ee84fea3b962d85935e72959e`.

Live Gatekeeper receipt: `6d2745727566163f9b65ca1d518e037e3409336b81ece8304e0d38ceea266ce8`.

Live measured Gatekeeper V2 evaluate hop: `36.22 ms`.

Live complete authority-transfer proof: `85.49 ms`.

Verified stages: V2 source pin PASS; fresh immutable ArtifactRef PASS; Agent A authenticated and denied with HTTP 403; same ArtifactRef handoff with `authority_transfer_from_artifact=false`; Agent B independently governed with HTTP 200; Gatekeeper `formal=permit` and `execution=allowed`; sealed receipt PASS; progressive evidence PASS; verdict preservation PASS; final `GATE_0` PASS with `authority_invariant=PASS` and `sponsor_development_unblocked=true`.

Commit `c64a6b183ecb499da4a784a54b5f7f99cfe86392` corrected `scripts/prove_gate0.py` to this boundary. A fresh Tenki claim, Cotal evidence, the historical public-edge signed-action 502 closure, sponsor integrations, chain verification, idempotency, and the Deterministic Steward implementation are not prerequisites for Core Gate 0. They remain separate supporting, sponsor, or security proof tracks and must not be represented as Gatekeeper authority.

## Deterministic Steward

Status: **IMPLEMENTATION PENDING**.

The Deterministic Steward is settled design and remains unimplemented. Tenki is not the Steward. Cotal is not the Steward. A Tenki worker, Cotal coordinator, sponsor adapter, or evidence aggregator must never be relabeled as the Deterministic Steward. The live Gate 0 proof correctly reported `IMPLEMENTATION_PENDING`, `authority=false`, and `core_gate_blocking=false`.

## Tenki

Platform/runtime status: **LIVE VERIFIED**. Fresh per-run binding status for the Gate 0 artifact above: **PENDING / non-blocking in that shell**.

Known-good snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`; sandbox/session `01a043be-5240-7bb3-a336-df794b64e56c`; worker port 8080. `POST /derive` previously succeeded with exact request fields `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. Tenki remains non-authoritative evidence with `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`.

Historical ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` is historical evidence only and must never be replayed for a new artifact.

Dynamic per-run binding is committed in `07a8d9c3cb2ce2b402dbe490232815159d0d0d49`, evidence forwarding in `daf388ee18ee51d5a1ef8b60cdc8094f9ee802c4`, current effect/principal binding in `eff2f1e004ea86b7f3d65c89cee4840c816c9dd8`, regression coverage in `bbbbbc306c7812d207dcc85ef0e23df328e59ab1` and `99bd9736fe4d3c14d2824b5674dc8c97d176d43f`, and judge UI in `130da411c856a35c3581ba089784687f59dc9563`.

## Cotal

Status: **LIVE where already proven**. Preserve its multi-principal identity/handoff role. Cotal coordinates and moves work; it does not grant Gatekeeper authority and it is not the Deterministic Steward.

## Public-edge signed-action 502

Status: **PENDING LIVE CLOSURE** and not a Core Gate 0 blocker.

The public edge is now running through nginx on port 8080. `/health` reaches Gatekeeper V2 successfully and an unsigned `POST /api/v2/actions/navigation` returns the expected `401 missing_agent_auth`, proving public-edge to action-edge routing. The live Gate 0 shell did not have signed diagnostic credentials, so `edge_signed_action` remained `PENDING`, `core_gate_blocking=false`.

Do not mark this track FIXED until a real signed public-edge request succeeds.

## Sponsor tracks

AIsa.ONE x Mitosis: **PENDING REAL INTEGRATION/PROOF**. Cloudflare: **PENDING REAL INTEGRATION/PROOF**. Nebius: **OPTIONAL / PENDING**. Core Gate 0 no longer blocks independent sponsor implementation. No sponsor may be shown as LIVE until its own real end-to-end result is proven. Sponsor outputs remain non-authoritative evidence or compute inputs and cannot assert authority, permit, capability, token, or Gatekeeper verdict.

## V2 pin

Source pin remains Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. The live Gate 0 run verified the actual checkout at exactly that commit. `runtime_identity_proven=false` remains explicit because immutable running process/image identity is not exposed by the current V2 health contract.

## Verification and CI

Live local Core Gate 0 proof is now verified and no longer pending. Existing executable evidence also includes the targeted Tenki authority-boundary tests, progressive evidence isolation tests, and nine-case signed-action diagnostic classifier suite.

**CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE.** Gatekeeper-V2-NPU was not modified.

## Next action

Core authority proof is complete. Advance independent sponsor and judge-facing integration work while separately closing the signed public-edge action track and refreshing live Tenki per-run evidence when the worker endpoint is available. Preserve the separation: Gatekeeper grants authority; Tenki computes derived evidence; Cotal coordinates; the Deterministic Steward remains implementation-pending until it actually exists.
