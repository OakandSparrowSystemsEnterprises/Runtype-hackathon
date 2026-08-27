# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Architecture boundary

`Gatekeeper-V2-NPU` is the source of truth. `Runtype-hackathon` is integration/demo shell only. Gatekeeper authority logic is not copied or reimplemented here. The minimal judge invariant remains raw bytes -> SHA-256 immutable ArtifactRef -> Agent A authenticated but execution denied -> same ArtifactRef handed to Agent B -> `authority_transfer_from_artifact=false` -> Agent B independently authorized -> real Gatekeeper permit/GREEN -> effect -> sealed receipt. Visible judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.** The two-agent case is the minimal invariant proof, not the target architecture. The target remains an OASSE Deterministic Steward coordinating a bounded swarm while Gatekeeper independently governs every effect.

The repaired V2 ontology remains a V2-owned source-of-truth artifact and is not duplicated into this repository.

## Day 2 judge UI

The judge path is verdict-first. `/api/demo/run` returns the authority-transfer result first. `/api/demo/evidence` resolves slower Tenki, Steward, Cotal, and governed-estate evidence afterward. `web/day2-arena.html` preserves the sealed Gatekeeper verdict even if supporting evidence later fails or times out.

Commit `130da411c856a35c3581ba089784687f59dc9563` finishes the live Tenki judge presentation. The UI distinguishes platform `LIVE VERIFIED` from the current-run derive result. A current-run Tenki claim is shown as LIVE only when `live=true`, `status=LIVE`, top-level `authority=false`, claim `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`. It surfaces claim kind, measured capacity, principal, requested effect, snapshot, and derive latency while continuing to identify Gatekeeper as the authority source.

Latency semantics remain separated. Prior direct Gatekeeper 50-run sample: 18.07 ms minimum, 22.70 ms p50, 24.65 ms mean, 36.45 ms p95, 48.29 ms maximum. Prior complete two-agent proof: about 240 ms. Prior full Arena/evidence orchestration: about 13.5 s. The action edge reports `gatekeeper_upstream_latency_ms`; the orchestrator separately reports full `authority_transfer_proof_ms`; Arena wall time is never presented as Gatekeeper latency.

## Tenki

Tenki is LIVE and independently verified. Fresh sandbox `01a043be-5240-7bb3-a336-df794b64e56c` was restored from snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`, originating from successful build `01a0410a-b9fe-7c5b-a79f-65848181b2b3` / template `gatekeeper-goi-worker-v2` (`01a04108-b541-7a1d-ba3d-e22c1479bca3`). Worker ran on port 8080. `POST /derive` succeeded. Tenki exec status was `SUCCEEDED`, exit code `0`, observed duration `19ms`.

The verified request body is exactly four fields: `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. No `authority`, `omega_res`, or `tau_ms` is sent. Worker defaults supplied `omega_res=256` and `tau_ms=25.0`, producing `capacity_bits_per_s=320.0` in the captured live response.

The historical successful response remains preserved in `evidence/tenki-live-derive-2026-08-27.json`. Its ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` is historical evidence only and must never be replayed for a new run.

Commit `07a8d9c3cb2ce2b402dbe490232815159d0d0d49` wires the dynamic per-run Tenki request in `src/demo-orchestrator/tenki_swarm.py`. Every fresh call derives `artifact_sha256` from the current immutable ArtifactRef and sends the current `requested_effect` and current `principal`. The old captured-response runtime path is removed. The adapter validates returned ArtifactRef, digest, effect, principal, `authority=false`, `compute_plane=tenki`, and `role=derived_claim_only`, while preserving the raw live response unchanged and recursively rejecting authority-like assertions including permit, capability, token, or Gatekeeper verdict.

Commit `daf388ee18ee51d5a1ef8b60cdc8094f9ee802c4` updates `src/demo-orchestrator/evidence_pipeline.py` so `/api/demo/evidence` passes the current run ArtifactRef, requested effect, and effect principal into Tenki independently of Cotal/estate evidence.

Commit `eff2f1e004ea86b7f3d65c89cee4840c816c9dd8` updates `src/demo-orchestrator/server.py` so the verdict cache carries `requested_effect=parent-shield.navigation` and `effect_principal=agent-b` from the actual current two-agent proof into the slower evidence phase. This does not transfer authority. It only carries the identity of the proposed governed effect being evaluated.

Commit `bbbbbc306c7812d207dcc85ef0e23df328e59ab1` updates `src/demo-orchestrator/test_tenki_swarm.py` for the exact verified four-field request contract and adds mismatch regression coverage for ArtifactRef, digest, effect, and principal. Commit `99bd9736fe4d3c14d2824b5674dc8c97d176d43f` updates `src/demo-orchestrator/test_evidence_pipeline.py` to verify that current-run ArtifactRef/effect/principal are forwarded to Tenki and that missing binding data fails before supporting work begins.

Runtime requirement: configure `TENKI_DERIVE_URL` to the reachable live worker `/derive` endpoint. `TENKI_STEWARD_URL` remains a compatibility fallback. If neither is configured, the current run reports supporting Tenki evidence unavailable rather than replaying historical evidence or manufacturing LIVE state.

## Signed-action 502

Missing authentication remains correctly `401 missing_agent_auth`. The historical signed path `502` is NOT marked fixed. `src/action-edge/server.py` preserves HMAC as its own verifier, capability gating, immutable ArtifactRef checks, and the real `action-edge -> GATEKEEPER_BASE_URL -> /api/domains/parent-shield/navigation/evaluate` call-home boundary. `/health/upstream` probes V2 from the action-edge process namespace without exposing the configured URL or credentials. Signed evaluation failures remain classified as `gatekeeper_unreachable`, `gatekeeper_invalid_response`, or `gatekeeper_timeout`.

`scripts/diagnose_action_edge.py` and its deterministic classifier regression suite remain the next runtime diagnostic path. Live 502 verification still requires the active Day 2 stack and a real signed governed artifact.

## V2 pin

`config/v2-source-pin.json` and `scripts/verify_v2_source_pin.py` retain the fail-closed source checkout pin at Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. Scope remains source checkout only. `runtime_identity_proven=false` is still explicit because immutable running process/image identity is not exposed by the current V2 runtime contract.

## Verification and CI

Existing targeted verification remains intact, including the Tenki authority-boundary suite, progressive evidence isolation suite, and nine-case signed-action diagnostic classifier suite. The new dynamic-request regression files are committed and statically aligned with the live request/response contract, but this connector-only run cannot clone or execute the branch because the execution container cannot resolve `github.com`; no false local green claim is made.

CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE. No no-op commit was created. Gatekeeper-V2-NPU was not modified.

## Next dependency

Best next action: set `TENKI_DERIVE_URL` in the active Day 2 orchestrator environment to the reachable live Tenki `/derive` endpoint, restart the orchestrator, and run one fresh `/api/demo/run` -> `/api/demo/evidence` cycle. The expected proof is a new ArtifactRef producing a new live Tenki derived claim bound to that same ArtifactRef, current `parent-shield.navigation` effect, and `agent-b`, while the Gatekeeper verdict remains already sealed and authoritative. After that, run `python3 scripts/diagnose_action_edge.py` to close the historical signed-action 502 track.
