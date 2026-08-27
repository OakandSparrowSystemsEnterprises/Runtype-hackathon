# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Architecture boundary

`Gatekeeper-V2-NPU` is the source of truth. `Runtype-hackathon` is integration/demo shell only. Do not copy or reimplement Gatekeeper authority logic here. The minimal judge invariant remains raw bytes -> SHA-256 immutable ArtifactRef -> Agent A authenticated but execution denied -> same ArtifactRef handed to Agent B -> `authority_transfer_from_artifact=false` -> Agent B independently authorized -> real Gatekeeper permit/GREEN -> effect -> sealed receipt. Visible judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.** This two-agent case is the minimal invariant proof, not the target architecture. The target remains an OASSE Deterministic Steward coordinating a bounded swarm while Gatekeeper independently governs every effect.

The V2 ontology was repaired in the source V2 workstream last night. That ontology remains a V2-owned artifact and is not duplicated into this repository. Any remaining ontology reasoner/release qualification belongs to the V2 source-of-truth track, not the hackathon integration shell.

## Day 2 judge UI

The judge path is verdict-first. `/api/demo/run` returns the authority-transfer result first. `/api/demo/evidence` resolves slower Tenki, Steward, Cotal, and governed-estate evidence afterward. `web/day2-arena.html` renders Gatekeeper immediately, preserves **THE ARTIFACT MOVED. AUTHORITY DID NOT.**, and prevents later evidence failure or timeout from erasing an already-sealed verdict. Tenki and Steward are separate from Cotal and from Gatekeeper. Tenki displays LIVE only when `live=true`, `status=LIVE`, and `authority=false`.

Latency semantics remain separated. Prior direct Gatekeeper 50-run sample: 18.07 ms minimum, 22.70 ms p50, 24.65 ms mean, 36.45 ms p95, 48.29 ms maximum. Prior complete two-agent proof: about 240 ms. Prior full Arena/evidence orchestration: about 13.5 s. The action edge reports `gatekeeper_upstream_latency_ms`; the orchestrator separately reports full `authority_transfer_proof_ms`; the UI does not present Arena wall time as Gatekeeper latency.

## Tenki

Tenki is now LIVE and independently verified. Fresh sandbox `01a043be-5240-7bb3-a336-df794b64e56c` was restored from known-good snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`, originating from successful build `01a0410a-b9fe-7c5b-a79f-65848181b2b3` / template `gatekeeper-goi-worker-v2` (`01a04108-b541-7a1d-ba3d-e22c1479bca3`). Worker ran on port 8080. `POST /derive` succeeded. Tenki exec status was `SUCCEEDED`, exit code `0`, observed duration `19ms`.

The exact verified live response is recorded in `evidence/tenki-live-derive-2026-08-27.json` and is the source of truth for the derive response contract. Its claim is `kind=goi_l0_boundary_capacity`, `compute_plane=tenki`, `role=derived_claim_only`, `authority=false`, with `capacity_bits_per_s=320.0`, `omega_res=256`, and `tau_ms=25.0`. The captured claim ArtifactRef is `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5`; this sample must never be replayed as evidence for a different ArtifactRef.

Commit `bd6823b6c6622f79c3ed941ed3a9c4f2470562e6` updates `src/demo-orchestrator/tenki_swarm.py` to validate the real live `{"claim":...,"ok":true}` response shape, preserve it verbatim under `raw`, expose the derived `claim`, require `authority=false`, require `compute_plane=tenki`, require `role=derived_claim_only`, and fail closed if the claim ArtifactRef does not match the governed ArtifactRef. Recursive rejection of authority-like assertions remains active for `authority`, `permit`, `capability`, `token`, and `gatekeeper_verdict`.

Commit `e743bd88f76310a2dc4155c2ff105036a0353885` updates the Tenki contract regression tests to use the exact verified live response structure and adds ArtifactRef mismatch protection. The repo does not contain the request body that produced the successful `/derive` response, so no new request shape has been invented. Per-run `/api/demo/evidence` live binding must call `/derive` using the actual worker request contract and the current run's ArtifactRef. The platform itself is LIVE; per-run derive request wiring remains the next integration dependency.

## Signed-action 502

Missing authentication remains correctly `401 missing_agent_auth`. The historical signed path `502` is NOT marked fixed. `src/action-edge/server.py` preserves HMAC as its own verifier, capability gating, immutable ArtifactRef checks, and the real `action-edge -> GATEKEEPER_BASE_URL -> /api/domains/parent-shield/navigation/evaluate` call-home boundary. `/health/upstream` probes V2 from the action-edge process namespace without exposing the configured URL or credentials. Signed evaluation failures are classified as `gatekeeper_unreachable`, `gatekeeper_invalid_response`, or `gatekeeper_timeout` rather than collapsing into an opaque gateway failure.

`scripts/diagnose_action_edge.py` distinguishes action-edge process failure, direct action-edge POST failure, public-edge-to-action-edge failure, direct V2 failure, action-edge namespace V2 reachability failure, signed V2 unreachable, invalid JSON response, timeout, and successful non-502 signed completion. Commit `8772b0f018e9ecafa0a437b2b6834ff69cc7c980` expanded `scripts/test_diagnose_action_edge.py` to nine deterministic classifier cases; those nine cases passed in targeted execution. Live 502 verification still requires the active Day 2 stack and real signed credentials/artifact.

## V2 pin

`config/v2-source-pin.json` and `scripts/verify_v2_source_pin.py` retain the fail-closed source checkout pin at Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. Scope is source checkout only. `runtime_identity_proven=false` remains explicit because immutable running process/image identity is not yet exposed by the V2 runtime contract.

## Verification and CI

Previously verified integration commits include `38162bf` Tenki swarm contract, `8f76854` progressive evidence pipeline, `2ed79cf` `/api/demo/evidence`, `c874297` Tenki authority-boundary tests, `7b2d47c` progressive judge UI, `80e5e28` evidence failure isolation, `2004817` verdict-preserving UI failure handling, `730125a` action-edge upstream health, `2fc6c9d` controlled invalid V2 response handling, `763a969` V2-hop latency, `6d56fa5` complete proof latency, `854273d` latency UI, `42d2cc5` recursive Tenki non-authority guard, `83f4771` nested authority regression coverage, and `d0f1251` progressive evidence regression coverage.

New live evidence commits: `bd6823b6` verified derive-response adapter contract, `c369119c` exact live Tenki evidence record, and `e743bd88` updated regression coverage against the live shape.

GitHub Actions CI remains conserved unless a final release checkpoint materially needs it. Gatekeeper-V2-NPU authority logic was not modified.

## Next dependency

Highest-value next dependency: capture or recover the exact request body/fields used for the successful Tenki `POST /derive`, then wire that request contract to the current Day 2 ArtifactRef so `/api/demo/evidence` performs a fresh per-run derive instead of replaying the verified sample. In parallel, run `python3 scripts/diagnose_action_edge.py` against the active Day 2 stack to close the historical signed-action 502 track.
