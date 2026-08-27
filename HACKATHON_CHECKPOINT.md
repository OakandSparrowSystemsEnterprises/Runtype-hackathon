# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Architecture boundary

`Gatekeeper-V2-NPU` is the source of truth. `Runtype-hackathon` is integration/demo shell only. Do not copy or reimplement Gatekeeper authority logic here. The minimal judge invariant remains raw bytes -> SHA-256 immutable ArtifactRef -> Agent A authenticated but execution denied -> same ArtifactRef handed to Agent B -> `authority_transfer_from_artifact=false` -> Agent B independently authorized -> real Gatekeeper permit/GREEN -> effect -> sealed receipt. Visible judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.** This two-agent case is the minimal invariant proof, not the target architecture. The target remains an OASSE Deterministic Steward coordinating a bounded swarm while Gatekeeper independently governs every effect.

The V2 ontology was repaired in the source V2 workstream last night. That ontology remains a V2-owned artifact and is not duplicated into this repository. Any remaining ontology reasoner/release qualification belongs to the V2 source-of-truth track, not the hackathon integration shell.

## Day 2 judge UI

The judge path is verdict-first. `/api/demo/run` returns the authority-transfer result first. `/api/demo/evidence` resolves slower Tenki, Steward, Cotal, and governed-estate evidence afterward. `web/day2-arena.html` renders Gatekeeper immediately, preserves **THE ARTIFACT MOVED. AUTHORITY DID NOT.**, and prevents later evidence failure or timeout from erasing an already-sealed verdict. Tenki and Steward are separate from Cotal and from Gatekeeper. Tenki displays LIVE only when `live=true`, `status=LIVE`, and `authority=false`. Steward remains IMPLEMENTATION PENDING unless backed by a genuine live non-authoritative Tenki result.

Latency semantics remain separated. Prior direct Gatekeeper 50-run sample: 18.07 ms minimum, 22.70 ms p50, 24.65 ms mean, 36.45 ms p95, 48.29 ms maximum. Prior complete two-agent proof: about 240 ms. Prior full Arena/evidence orchestration: about 13.5 s. The action edge now reports `gatekeeper_upstream_latency_ms`; the orchestrator separately reports full `authority_transfer_proof_ms`; the UI explicitly does not present Arena wall time as Gatekeeper latency.

## Tenki

Known-good Tenki checkpoint: template `gatekeeper-goi-worker-v2`, template ID `01a04108-b541-7a1d-ba3d-e22c1479bca3`, successful build `01a0410a-b9fe-7c5b-a79f-65848181b2b3`, snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`, worker start command `python3 /home/tenki/gatekeeper-tenki/worker.py`.

Repository integration is READY. `src/demo-orchestrator/tenki_swarm.py` builds the OASSE swarm-plan contract, leaves live execution `NEXT_PENDING` without a real endpoint, preserves any genuine live worker response verbatim under `raw`, and rejects authority-like assertions recursively anywhere in Tenki/Steward output. Rejected fields include `authority`, `permit`, `capability`, `token`, and `gatekeeper_verdict` when asserted with values other than null/false. `src/demo-orchestrator/evidence_pipeline.py` keeps Tenki in the slower phase and failure-isolates Tenki from Cotal/estate evidence.

Live Tenki worker status remains PENDING. The next real step is to create a fresh sandbox from snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`, hit the worker, capture its actual derived GOI response, and bind exactly that live structure into `/api/demo/evidence`. No live payload shape has been invented.

## Signed-action 502

Missing authentication remains correctly `401 missing_agent_auth`. The historical signed path `502` is NOT marked fixed. `src/action-edge/server.py` preserves HMAC as its own verifier, capability gating, immutable ArtifactRef checks, and the real `action-edge -> GATEKEEPER_BASE_URL -> /api/domains/parent-shield/navigation/evaluate` call-home boundary. `/health/upstream` probes V2 from the action-edge process namespace without exposing the configured URL or credentials. Signed evaluation failures are classified as `gatekeeper_unreachable`, `gatekeeper_invalid_response`, or `gatekeeper_timeout` rather than collapsing into an opaque gateway failure.

`scripts/diagnose_action_edge.py` now distinguishes action-edge process failure, direct action-edge POST failure, public-edge-to-action-edge failure, direct V2 failure, action-edge namespace V2 reachability failure, signed V2 unreachable, invalid JSON response, timeout, and successful non-502 signed completion. Commit `8772b0f018e9ecafa0a437b2b6834ff69cc7c980` expands `scripts/test_diagnose_action_edge.py` to nine deterministic classifier cases. All nine cases passed in targeted execution on this run. Live 502 verification still requires the active Day 2 stack and real signed credentials/artifact.

## V2 pin

`config/v2-source-pin.json` and `scripts/verify_v2_source_pin.py` retain the fail-closed source checkout pin at Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. Scope is source checkout only. `runtime_identity_proven=false` remains explicit because immutable running process/image identity is not yet exposed by the V2 runtime contract. No V2 core change has been made to manufacture that identity.

## Verification and CI

Previously verified integration commits include `38162bf` Tenki swarm contract, `8f76854` progressive evidence pipeline, `2ed79cf` `/api/demo/evidence`, `c874297` Tenki authority-boundary tests, `7b2d47c` progressive judge UI, `80e5e28` evidence failure isolation, `2004817` verdict-preserving UI failure handling, `730125a` action-edge upstream health, `2fc6c9d` controlled invalid V2 response handling, `763a969` V2-hop latency, `6d56fa5` complete proof latency, `854273d` latency UI, `42d2cc5` recursive Tenki non-authority guard, and `83f4771` nested authority regression coverage.

Targeted deterministic verification this run: 9/9 signed-action diagnostic classifier cases PASS. GitHub Actions CI was intentionally skipped to conserve Actions usage. No no-op commit was created. Gatekeeper-V2-NPU was not modified.

## Next dependency

Best live next action: run `python3 scripts/diagnose_action_edge.py` against the active Day 2 stack. If the signed path no longer reproduces 502/504, report only `SIGNED_PROBE_COMPLETED`, not FIXED, until the governed action is verified end-to-end. After that, launch the known-good Tenki snapshot and capture the real worker response for exact `/api/demo/evidence` binding.
