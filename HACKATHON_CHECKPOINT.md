# Gatekeeper V2 Agent Native Builders Checkpoint

Updated: 2026-08-27
Branch: `day2-progressive-arena-2026-08-26`

The frozen judge invariant is the two-agent authority-transfer proof: raw bytes become a SHA-256/content-addressed immutable ArtifactRef; Agent A is authenticated but denied execution; the same ArtifactRef is handed to Agent B; `authority_transfer_from_artifact=false`; Agent B is independently authorized; Gatekeeper returns the real GREEN/permit result; the effect produces a sealed receipt. The visible line remains: **THE ARTIFACT MOVED. AUTHORITY DID NOT.** This is the minimal proof case, not the target architecture.

The target architecture is a swarm-native OASSE Deterministic Steward running substantive bounded compute on Tenki. The Steward decides what work the swarm should attempt and tracks deterministic state, provenance, timing, aggregation, and failure isolation. Gatekeeper remains the only authority boundary for effects. Cotal remains a coordination/handoff integration and must not be described as the OASSE Deterministic Steward.

Progressive Day 2 UX exists on this branch. The base `/api/demo/run` path returns the Gatekeeper authority-transfer result first and caches it by `run_id`; `/api/demo/evidence` is the slower evidence phase. Direct Gatekeeper latency remains the measured tens-of-milliseconds path (18.07 ms min, 22.70 ms p50, 24.65 ms mean, 36.45 ms p95, 48.29 ms max from the latest 50-run sample). The two-agent proof is about 240 ms. The prior full Arena orchestration was about 13.5 s. Arena wall time must never be labeled Gatekeeper latency.

Tenki remote checkpoint is recovered and must not be rebuilt unnecessarily: template `gatekeeper-goi-worker-v2`, template ID `01a04108-b541-7a1d-ba3d-e22c1479bca3`, successful build `01a0410a-b9fe-7c5b-a79f-65848181b2b3`, snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098`, start command `python3 /home/tenki/gatekeeper-tenki/worker.py`. The remaining live step is to create a fresh Tenki sandbox from that successful snapshot, capture the actual worker response, then bind the real response shape without inventing it.

Repository-side Tenki work completed in this run: `src/demo-orchestrator/tenki_swarm.py` defines the OASSE-owned swarm plan contract, explicitly marks every worker result as non-authoritative, preserves the upstream live response verbatim under `raw`, rejects attempts to manufacture authority/permit/capability/Gatekeeper verdict, and stays `NEXT_PENDING` when no real Tenki Steward endpoint exists. `src/demo-orchestrator/evidence_pipeline.py` runs the existing slower Cotal/estate evidence and the Tenki swarm plane concurrently after the base verdict, reports `supporting_evidence_ms`, and keeps Deterministic Steward status `IMPLEMENTATION_PENDING` until the Tenki plane is genuinely live.

Commits created this run: `38162bfef77e9b0ef0a69604098145a9eff468d2` (Tenki swarm orchestration contract) and `8f7685417df2ae6ba5a267c352f9c480d56050be` (progressive evidence pipeline with Tenki swarm plane).

Verification this run: the Tenki swarm module was syntax-compiled before commit. No live Tenki execution was claimed. No certified/private Gatekeeper V2 core files were changed.

Known blocker and next dependency: `/api/demo/evidence` still invokes the legacy `run_arena` path directly. The next repository unit is to wire `run_progressive_evidence` into that route and update the Day 2 UI to show Tenki/Steward swarm progress independently. Live Tenki remains pending until the snapshot is launched and its actual response is captured. Public signed-action `502 Bad Gateway` remains an explicit unresolved hardening track and has not been marked fixed.
