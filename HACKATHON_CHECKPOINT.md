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

The canonical Windows launcher is `scripts/start_day2.ps1`. It starts the artifact boundary, action edge, arena orchestrator, and nginx public edge in one aligned environment, can generate ephemeral hackathon HMAC identities without printing them, checks V2 and action-edge upstream health, and can run Gate 0 or the Steward proof in the same environment.

## Deterministic Steward

Status: **IMPLEMENTED / LIVE PARTIAL PROOF VERIFIED**.

The Steward is now real repository code in `src/demo-orchestrator/deterministic_steward.py`; it is no longer inferred from Tenki status. The latest local proof returned `implemented=true`, `swarm_native=true`, `authority=false`, a stable `plan_id`, a deterministic `state_hash`, Cotal coordination worker PASS, and no failed workers. That proof was PARTIAL only because no live Tenki swarm endpoints were configured in that shell.

The Steward now plans one Cotal coordination worker plus a fixed-width Tenki replica pool. The default Tenki width is four, so the default plan is five first-class workers. Completion order and timing remain visible provenance but are excluded from deterministic state hashing. Worker failures are isolated and preserved rather than collapsing the whole aggregate. Gatekeeper remains the only authority source for effects.

Key commits: `5905a19f3fb2ea7beee32b1c78f169073d239e5a` initial Steward module; `d8fab4ed8a11322522690393b8180c88e2537ffd` deterministic hash-boundary correction; `9701c3e1bd12d7428d377005e53deb007ef50f7a` first-class Tenki replica workers; `c7b1d95c01767bd1c8de2c15af5d921a7c91c9f3` live proof upgraded to require replica consensus when endpoints are configured.

## Tenki

Platform/runtime status: **LIVE VERIFIED**. Multi-replica swarm runtime status: **READY TO LAUNCH / LIVE PROOF PENDING**.

Known-good snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`; historical successful sandbox/session `01a043be-5240-7bb3-a336-df794b64e56c`; worker port 8080. `POST /derive` previously succeeded with exact request fields `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. Tenki remains non-authoritative evidence with `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`.

The new Tenki workload is a deterministic replica swarm, not invented worker semantics. Every replica independently receives the same exact governed `/derive` request for the fresh ArtifactRef/effect/principal. The Steward requires claim-hash consensus and preserves failed/pending replicas independently. Full Tenki swarm LIVE requires the configured replica width to complete against distinct live `/derive` endpoints.

`scripts/launch_tenki_swarm.ps1` now restores multiple sandboxes from the verified snapshot, starts `python3 /home/tenki/gatekeeper-tenki/worker.py` in each sandbox, exposes port 8080, collects the returned preview URLs, and populates `TENKI_DERIVE_URLS` plus `TENKI_SWARM_WIDTH` for the current PowerShell session. Commits: `319954f14a837560d12aa8c8f35ac3fc7237465e` replica-swarm runtime; `8b58a923ae58da421b4c51b980bdfb6a31e4a9f2` real Tenki sandbox launcher; `2fcf8cc264ae2856883cf244580ed4b8ae4b48a9` launcher compatibility pointer.

Historical ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` is historical evidence only and must never be replayed for a new artifact.

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

Live local Core Gate 0 proof is verified. Live signed public-edge action is verified. Deterministic Steward implementation has a live PARTIAL proof with Cotal active and Tenki replicas pending. The next live proof is the four-replica Tenki swarm consensus run.

**CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE.** Gatekeeper-V2-NPU was not modified.

## Next action

Launch the real Tenki replica swarm from the verified snapshot in the current PowerShell session, then rerun the canonical Steward proof. Full Steward LIVE requires Cotal coordination plus all configured Tenki replicas completing with deterministic GOI claim-hash consensus while every worker remains `authority=false`.
