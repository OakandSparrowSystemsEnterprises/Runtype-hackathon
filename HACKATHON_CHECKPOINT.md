# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27. Branch: `day2-progressive-arena-2026-08-26`.

## Authority boundary

`Gatekeeper-V2-NPU` remains the sole authority source. `Runtype-hackathon` is integration/demo shell only. The minimal invariant is fresh bytes -> immutable SHA-256 ArtifactRef -> Agent A authenticated but denied -> same ArtifactRef handed off -> `authority_transfer_from_artifact=false` -> Agent B independently governed by real V2 -> bounded effect -> sealed receipt. Judge line: **THE ARTIFACT MOVED. AUTHORITY DID NOT.** The target architecture remains the OASSE Deterministic Steward coordinating bounded swarm compute while Gatekeeper independently governs effects.

The repaired ontology remains V2-owned and is not duplicated here.

## Gate status

Current proof gate: **GATE 0 CORE FIRST — PENDING LIVE FRESH PROOF**.

Sponsor eligibility: **NONE until Gate 0 PASS**. AIsa.ONE x Mitosis is Gate 1 and may begin only after a full Gate 0 PASS. Cloudflare remains locked behind Gate 1 PASS. Nebius remains optional and locked behind Gate 2 PASS.

Commit `57d5a1694d1b35690387cc64cb09957d2cb1f820` added `scripts/prove_gate0.py`, the fail-closed end-to-end proof runner. Commit `9ef8facf7e1875b9e04db1df09165efa8778fa33` fixes its bootstrap ordering: Gate 0 now creates a fresh ArtifactRef first and binds the signed-action diagnostic to that exact artifact. A historical `DIAGNOSTIC_ARTIFACT_REF` is no longer a precondition and cannot accidentally satisfy freshness. The runner also accepts the matching agent key from `GATEKEEPER_AGENT_KEYS_JSON` when `DIAGNOSTIC_AGENT_SECRET` is not separately duplicated into the shell.

The runner still refuses PASS unless the Gatekeeper-V2-NPU source checkout matches the pinned commit; a real signed action completes without reproducing the historical 502/504; the fresh `/api/demo/run` returns a valid fresh ArtifactRef; Agent A is denied with 403; Agent B succeeds with 200; artifact possession does not transfer authority; V2 returns allowed/permit plus a sealed artifact hash; `/api/demo/evidence` preserves the verdict; Tenki resolves LIVE and non-authoritative for the exact same fresh ArtifactRef/digest/effect/principal; and the Deterministic Steward resolves LIVE with `authority=false`. Only then may it emit `GATE_0: PASS` and mark `AISA.ONE x MITOSIS` eligible.

No sponsor integration has been started because Gate 0 has not yet produced the required serial PASS.

## Tenki

Tenki platform/runtime is independently **LIVE VERIFIED**. Fresh sandbox `01a043be-5240-7bb3-a336-df794b64e56c` was restored from snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`; worker port 8080; `POST /derive` succeeded; Tenki exec `SUCCEEDED`, exit code 0, observed duration 19ms.

The verified request has exactly `artifact_ref`, `artifact_sha256`, `requested_effect`, and `principal`. Dynamic per-run binding is committed in `07a8d9c3cb2ce2b402dbe490232815159d0d0d49`, evidence forwarding in `daf388ee18ee51d5a1ef8b60cdc8094f9ee802c4`, current effect/principal cache binding in `eff2f1e004ea86b7f3d65c89cee4840c816c9dd8`, regression coverage in `bbbbbc306c7812d207dcc85ef0e23df328e59ab1` and `99bd9736fe4d3c14d2824b5674dc8c97d176d43f`, and judge UI in `130da411c856a35c3581ba089784687f59dc9563`.

Historical ArtifactRef `sha256:5386fdfcbc233f3b8da8ba274651d2174aa233e88dc4d35948f2189923f652e5` remains evidence only and must never be replayed against a new run. Every Gate 0 proof must obtain a fresh claim for the current ArtifactRef.

## Day 2 UX

The judge flow is verdict-first. `/api/demo/run` renders Gatekeeper before `/api/demo/evidence`. Supporting Tenki, Steward, Cotal, estate, chain, and replay evidence cannot erase an already sealed verdict. Gatekeeper V2 hop latency and full authority-transfer proof latency remain separately measured. Arena/evidence wall time is never reported as Gatekeeper latency.

## Signed-action 502

Status: **PENDING LIVE CLOSURE**. Missing auth is correctly `401 missing_agent_auth`. The action edge retains HMAC verification, capability gating, immutable ArtifactRef validation, and the real `action-edge -> GATEKEEPER_BASE_URL -> /api/domains/parent-shield/navigation/evaluate` boundary. Runtime diagnostics distinguish action-edge process failure, public-edge routing, action-edge namespace V2 reachability, V2 unreachable, invalid response, timeout, and successful signed completion. Gate 0 now runs that signed diagnostic against the exact fresh artifact created by the proof attempt instead of requiring a manually supplied prior ArtifactRef.

## V2 pin

Source pin remains Gatekeeper-V2-NPU commit `338a126521a8427fe5d1988d0a1381affe8c75bd`. `scripts/verify_v2_source_pin.py` is fail-closed. Scope is source checkout identity; runtime process/image identity remains explicitly unproven by the current V2 health contract.

## Verification and CI

The committed `scripts/prove_gate0.py` at blob `25240ee31b86057b9273925125e10e2cde043d27` was fetched back from the branch after the update and inspected for the fresh-artifact-first ordering, exact ArtifactRef injection into `diagnose_action_edge.py`, and secret fallback behavior. Live end-to-end execution is intentionally not claimed from the connector environment because it cannot reach the user's localhost/Tenki/V2 processes.

Existing targeted suites remain the latest executable evidence: Tenki authority-boundary tests, progressive evidence isolation tests, and the nine-case signed-action diagnostic classifier suite.

**CI INTENTIONALLY SKIPPED TO CONSERVE GITHUB ACTIONS USAGE.** No no-op commit was made and Gatekeeper-V2-NPU was not modified.

## Next action

Pull the branch head and run `python .\scripts\prove_gate0.py` from the active Day 2 shell with `GATEKEEPER_V2_SOURCE_ROOT`, `TENKI_DERIVE_URL`, and the same `GATEKEEPER_AGENT_KEYS_JSON` used by the running hackathon services. `DIAGNOSTIC_ARTIFACT_REF` is no longer required. Do not start AIsa.ONE x Mitosis unless that command emits `GATE_0` with `PASS`.
