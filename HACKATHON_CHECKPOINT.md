# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Authority boundary

`Gatekeeper-V2-NPU` remains the sole authority source. `Runtype-hackathon` is integration/demo shell only. The core invariant is fresh bytes -> immutable SHA-256 ArtifactRef -> Agent A authenticated and denied -> same ArtifactRef handed off -> `authority_transfer_from_artifact=false` -> Agent B independently governed by real V2 -> Gatekeeper permit/GREEN/allowed result -> bounded effect -> sealed receipt. Judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.**

The repaired ontology remains V2-owned and is not duplicated here.

## Core Gate 0

Status: **PASS — LIVE LOCAL PROOF VERIFIED 2026-08-27**.

Most recent canonical launcher proof ArtifactRef: `sha256:0faa19559edec5195bc54d81045872aeeb0d8c8314b3f20189709c9133a01852`.

Most recent Gatekeeper receipt: `561fe5ca28bd279780840c6cfddc663e2e5f3836d00ec4768720eeea2e71a2f7`.

Measured Gatekeeper V2 evaluate hop: `24.65 ms`.

Complete authority-transfer proof: `105.62 ms`.

Verified stages: V2 source pin PASS; fresh immutable ArtifactRef PASS; Agent A authenticated and denied with HTTP 403; same ArtifactRef handoff with `authority_transfer_from_artifact=false`; Agent B independently governed with HTTP 200; Gatekeeper `formal=permit` and `execution=allowed`; sealed receipt PASS; progressive evidence PASS; verdict preservation PASS; final `GATE_0` PASS with `authority_invariant=PASS` and `sponsor_development_unblocked=true`.

The canonical Windows launcher is `scripts/start_day2.ps1`. It starts the artifact boundary, action edge, orchestrator, and nginx public edge in one aligned environment, can generate ephemeral hackathon HMAC identities without printing them, checks V2 and action-edge upstream health, and with `-RunGate0` executes the fresh authority proof in the same environment.

## Deterministic Steward

Status: **IMPLEMENTATION PENDING**.

The Deterministic Steward is settled design and remains unimplemented. Tenki is not the Steward. Cotal is not the Steward. A Tenki worker, Cotal coordinator, sponsor adapter, or evidence aggregator must never be relabeled as the Deterministic Steward. The live Gate 0 proof correctly reports `IMPLEMENTATION_PENDING`, `authority=false`, and `core_gate_blocking=false`.

## Tenki

Platform/runtime status: **LIVE VERIFIED**. Fresh per-run binding status for the current canonical Gate 0 artifact: **PENDING / non-blocking**.

Known-good snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`; sandbox/session `01a043be-5240-7bb3-a336-df794b64e56c`; worker port 8080. `POST /derive` previously succeeded with exact request fields `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. Tenki remains non-authoritative evidence with `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`.

Historical ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` is historical evidence only and must never be replayed for a new artifact.

Dynamic per-run binding is committed in `07a8d9c3cb2ce2b402dbe490232815159d0d0d49`, evidence forwarding in `daf388ee18ee51d5a1ef8b60cdc8094f9ee802c4`, current effect/principal binding in `eff2f1e004ea86b7f3d65c89cee4840c816c9dd8`, regression coverage in `bbbbbc306c7812d207dcc85ef0e23df328e59ab1` and `99bd9736fe4d3c14d2824b5674dc8c97d176d43f`, and judge UI in `130da411c856a35c3581ba089784687f59dc9563`.

## Cotal

Status: **LIVE where already proven**. Preserve its multi-principal identity/handoff role. Cotal coordinates and moves work; it does not grant Gatekeeper authority and it is not the Deterministic Steward.

## Public-edge signed-action track

Status: **PASS — LIVE SIGNED REQUEST VERIFIED 2026-08-27**.

The canonical launcher brought up nginx on port 8080 and the full signed path completed successfully against the exact fresh Gate 0 ArtifactRef `sha256:0faa19559edec5195bc54d81045872aeeb0d8c8314b3f20189709c9133a01852`.

Verified public-edge evidence: action-edge health HTTP 200; action-edge Gatekeeper upstream health HTTP 200 with `reachable_from_action_edge=true` and `parent_shield_mounted=true`; direct unsigned action HTTP 401 `missing_agent_auth`; public unsigned action HTTP 401 `missing_agent_auth`; signed public action HTTP 200; signed principal `agent-b`; capability `parent-shield.navigation`; `authority_transfer_from_artifact=false`; Gatekeeper `formal=permit`, `product=GREEN`, `execution=allowed`; action-edge measured signed V2 hop `58.22 ms`; final diagnostic `SIGNED_PROBE_COMPLETED`.

The historical signed-action 502 did not reproduce under the aligned canonical stack. Treat this track as closed for the verified local Day 2 topology. Runtime image/process identity remains explicitly unproven.

## Sponsor tracks

AIsa.ONE x Mitosis: **PENDING REAL INTEGRATION/PROOF**. Cloudflare: **PENDING REAL INTEGRATION/PROOF**. Nebius: **OPTIONAL / PENDING**. Core Gate 0 no longer blocks independent sponsor implementation. No sponsor may be shown as LIVE until its own real end-to-end result is proven. Sponsor outputs remain non-authoritative evidence or compute inputs and cannot assert authority, permit, capability, token, or Gatekeeper verdict.

## V2 pin

Source pin remains Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. The live Gate 0 run verified the actual checkout at exactly that commit. `runtime_identity_proven=false` remains explicit because immutable running process/image identity is not exposed by the current V2 health contract.

## Verification and CI

Live local Core Gate 0 proof is verified. Live signed public-edge action is verified. Existing executable evidence also includes the targeted Tenki authority-boundary tests, progressive evidence isolation tests, and nine-case signed-action diagnostic classifier suite.

**CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE.** Gatekeeper-V2-NPU was not modified.

## Next action

Core authority proof and signed public-edge closure are complete. Advance independent sponsor and judge-facing integration work while refreshing live Tenki per-run evidence when the worker endpoint is available. Preserve the separation: Gatekeeper grants authority; Tenki computes derived evidence; Cotal coordinates; the Deterministic Steward remains implementation-pending until it actually exists.
