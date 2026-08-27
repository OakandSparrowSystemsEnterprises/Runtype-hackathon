# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Authority boundary

`Gatekeeper-V2-NPU` remains the sole authority source. `Runtype-hackathon` is integration/demo shell only. The core invariant is fresh bytes -> immutable SHA-256 ArtifactRef -> Agent A authenticated and denied -> same ArtifactRef handed off -> `authority_transfer_from_artifact=false` -> Agent B independently governed by real V2 -> Gatekeeper permit/GREEN/allowed result -> bounded effect -> sealed receipt. Judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.**

The repaired ontology remains V2-owned and is not duplicated here.

## Core Gate 0

Status: **PASS - LIVE LOCAL PROOF VERIFIED 2026-08-27**.

Most recent canonical launcher proof ArtifactRef: `sha256:0faa19559edec5195bc54d81045872aeeb0d8c8314b3f20189709c9133a01852`.

Most recent Gatekeeper receipt: `561fe5ca28bd279780840c6cfddc663e2e5f3836d00ec4768720eeea2e71a2f7`.

Measured Gatekeeper V2 evaluate hop: `24.65 ms`.

Complete authority-transfer proof: `105.62 ms`.

Verified stages: V2 source pin PASS; fresh immutable ArtifactRef PASS; Agent A authenticated and denied with HTTP 403; same ArtifactRef handoff with `authority_transfer_from_artifact=false`; Agent B independently governed with HTTP 200; Gatekeeper `formal=permit` and `execution=allowed`; sealed receipt PASS; progressive evidence PASS; verdict preservation PASS; final `GATE_0` PASS with `authority_invariant=PASS` and `sponsor_development_unblocked=true`.

The canonical Windows launcher is `scripts/start_day2.ps1`. It starts the artifact boundary, action edge, arena orchestrator, and nginx public edge in one aligned environment, can generate ephemeral hackathon HMAC identities without printing them, checks V2 and action-edge upstream health, and can run Gate 0 in the same environment.

## Deterministic Steward

Status: **IMPLEMENTATION PENDING**.

The Steward remains a settled design only. It is not a Gate 0 requirement, not a Tenki alias, and Cotal must not impersonate it. `scripts/start_day2.ps1 -RunSteward` now reports `IMPLEMENTATION_PENDING` without executing a Steward proof. Progressive evidence also reports the Steward as `implemented=false`, `authority=false`, and `role=settled_design_only`.

Any experimental Steward code still present in the branch is not part of the active runtime contract and must not be represented to judges as implemented or live.

## Tenki

Platform/runtime status: **LIVE VERIFIED historically**. Fresh per-run binding status: **REPOSITORY PATH READY / LIVE LOCAL VERIFICATION PENDING**.

Known-good snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`; historical successful sandbox/session `01a043be-5240-7bb3-a336-df794b64e56c`; worker port 8080. `POST /derive` previously succeeded with exact request fields `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. Tenki remains non-authoritative evidence with `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`.

`src/demo-orchestrator/evidence_pipeline.py` binds the exact current `/api/demo/run` identity directly into `run_tenki_swarm`: fresh `artifact_ref`, current `requested_effect`, and current `effect_principal`. `tenki_swarm.py` derives and validates the matching `artifact_sha256` and rejects claims that do not match the exact current artifact/effect/principal or that attempt to assert authority. Historical captured claims are never replayed against a fresh ArtifactRef.

The progressive evidence path preserves Gatekeeper's already-returned verdict while Tenki, Cotal, and sponsor evidence resolve independently. A Tenki or sponsor failure remains non-authoritative supporting-evidence failure and cannot erase or replace the sealed Gatekeeper verdict.

Four Tenki sandbox sessions were created/adopted locally during the swarm work, but the restored sessions did not expose live `/derive` workers because Tenki `sandbox exec` repeatedly failed with `write envelope: EOF`; SSH also failed certificate verification. Do not treat those endpoints as LIVE. The existing `gatekeeper-goi-worker-v2` template is known to contain `start_cmd = python3 /home/tenki/gatekeeper-tenki/worker.py`, so the next Tenki runtime attempt should use the template-native startup path rather than another snapshot-plus-exec loop.

Historical ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` is historical evidence only and must never be replayed for a new artifact.

## Cotal

Status: **LIVE where already proven**. Preserve its multi-principal identity/handoff role. Cotal coordinates and moves work; it does not grant Gatekeeper authority and it is not the Deterministic Steward.

## Public-edge signed-action track

Status: **CLOSED - LIVE SIGNED REQUEST VERIFIED 2026-08-27**.

The canonical launcher brought up nginx on port 8080 and the full signed path completed successfully against the exact fresh Gate 0 ArtifactRef `sha256:0faa19559edec5195bc54d81045872aeeb0d8c8314b3f20189709c9133a01852`.

Verified public-edge evidence: action-edge health HTTP 200; action-edge Gatekeeper upstream health HTTP 200 with `reachable_from_action_edge=true` and `parent_shield_mounted=true`; direct unsigned action HTTP 401 `missing_agent_auth`; public unsigned action HTTP 401 `missing_agent_auth`; signed public action HTTP 200; signed principal `agent-b`; capability `parent-shield.navigation`; `authority_transfer_from_artifact=false`; Gatekeeper `formal=permit`, `product=GREEN`, `execution=allowed`; action-edge measured signed V2 hop `58.22 ms`; final diagnostic `SIGNED_PROBE_COMPLETED`.

The historical signed-action 502 did not reproduce under the aligned canonical stack. Treat this track as closed unless regression evidence appears. Runtime image/process identity remains explicitly unproven.

## Sponsor tracks

AIsa.ONE x Mitosis: **REPOSITORY ADAPTER + PROGRESSIVE PIPELINE INTEGRATION READY / LIVE PROOF PENDING**. `src/demo-orchestrator/sponsor_aisa_mitosis.py` performs one real AIsa Exa search, hashes the returned payload, and writes a non-authoritative observation into a Mitosis Cortex through the `mi` CLI. `evidence_pipeline.py` now executes this sponsor path concurrently with Tenki and the existing Cotal/estate evidence after the Gatekeeper verdict is already known. Missing credentials, missing office configuration, AIsa failure, or Mitosis write failure remain truthful `PENDING` or isolated `FAILED` states and cannot alter the sealed Gatekeeper verdict. A sponsor result becomes `LIVE` only when both the AIsa call and the Mitosis write complete. The adapter never emits permit, token, capability grant, or Gatekeeper verdict fields and explicitly keeps `authority=false`.

The adapter expects `AISA_API_KEY` plus `MITOSIS_OFFICE_ID` or `MI_OFFICE_ID`, and an authenticated Mitosis `mi` CLI on PATH. Targeted behavioral coverage includes missing credentials, successful AIsa-to-Mitosis packaging, Mitosis failure without false LIVE promotion, progressive sponsor isolation, and preservation of Gatekeeper/Tenki state when sponsor execution fails.

Cloudflare: **REPOSITORY EDGE WORKER READY / LIVE DEPLOYMENT PROOF PENDING**. `cloudflare/edge-worker.js` is a real reverse-proxy Worker entrypoint for the Arena/action path. It preserves inbound signed agent headers, forwards the original method/body/path/query to `OASSE_ORIGIN_URL`, marks Cloudflare's edge role explicitly, disables caching on responses, exposes `/__oasse/edge-health`, and states `authority=false` with `Gatekeeper-V2-NPU` as the authority source. `cloudflare/wrangler.toml` provides a deployable Workers configuration. Cloudflare remains PENDING until the Worker is actually deployed against a reachable origin and a signed governed request is proven through it.

Nebius: **OPTIONAL / PENDING**. Core Gate 0 no longer blocks independent sponsor implementation. No sponsor may be shown as LIVE until its own real end-to-end result is proven. Sponsor outputs remain non-authoritative evidence or compute inputs and cannot assert authority, permit, capability, token, or Gatekeeper verdict.

## V2 pin

Source pin remains Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. The live Gate 0 run verified the actual checkout at exactly that commit. `runtime_identity_proven=false` remains explicit because immutable running process/image identity is not exposed by the current V2 health contract.

## Verification and CI

Live local Core Gate 0 proof is verified. Live signed public-edge action is verified and the public-edge track is closed. The direct fresh Tenki binding path is restored repository-side and still needs one live local run against a template-started Tenki worker. Cotal remains LIVE where already proven. Deterministic Steward remains IMPLEMENTATION PENDING. AIsa.ONE x Mitosis is wired into progressive evidence but remains PENDING until real credentials and a real Mitosis write are exercised locally. Cloudflare has a substantive repository-side gateway implementation but remains PENDING until deployment and a signed request through the Worker are proven.

Targeted checks executed for the latest repository work: Python behavioral harness PASS for sponsor progressive isolation and Gatekeeper verdict preservation; Node `--check` PASS for `cloudflare/edge-worker.js`; Cloudflare Worker local contract harness PASS for health authority boundary and truthful 503/PENDING behavior when `OASSE_ORIGIN_URL` is absent. **CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE.** Gatekeeper-V2-NPU was not modified.

## Next action

Use the existing `gatekeeper-goi-worker-v2` Tenki template startup path to obtain one live `/derive` endpoint, export it as `TENKI_DERIVE_URL`, and run the normal `/api/demo/run` plus progressive-evidence path. The live proof must show the new run's ArtifactRef, matching artifact SHA-256, current effect, and current principal in the returned Tenki claim with `authority=false`.

In parallel, configure `AISA_API_KEY` and `MITOSIS_OFFICE_ID` (or `MI_OFFICE_ID`) with an authenticated `mi` CLI and run the normal progressive evidence path so the already-integrated sponsor adapter can truthfully move from PENDING to LIVE. For Cloudflare, deploy `cloudflare/wrangler.toml` with `OASSE_ORIGIN_URL` set to a reachable Arena/action origin, then prove one signed governed request through the Worker and capture `/__oasse/edge-health`. If either deployment becomes infrastructure surgery, preserve the repository-ready PENDING state and move to judge UX/submission packaging rather than risking the submission window.
