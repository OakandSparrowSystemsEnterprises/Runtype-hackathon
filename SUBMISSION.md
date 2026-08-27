# Gatekeeper V2 — Agent-Native Universal Artifact Authority

**Agent Native Builders Hackathon @ Cloudflare HQ · August 26–27, 2026 · Oak & Sparrow Systems Enterprise**

> **Work can move between agents. Authority does not move with it.**

Agents exchange artifacts, coordinate over messaging fabrics, and fan work out to external compute, but no content, credential possession, coordination message, or compute result ever grants the authority to act. Every consequential effect is resolved by Gatekeeper V2 **before execution** and leaves a sealed, hash-chained, replayable receipt. Denials get the same receipts as permits.

## The 60-second judge path

1. Open the Day 2 Arena (public edge `/`, served by nginx; use the Cloudflare tunnel URL only when the Cloudflare edge script is actually running and the response carries Cloudflare runtime evidence).
2. Click **RUN DAY 2 DEMO**. One live run turns fresh bytes into an immutable SHA-256 ArtifactRef; Agent A is authenticated and **denied (HTTP 403, no capability)**; the same artifact is handed to Agent B with `authority_transfer_from_artifact=false`; Agent B is independently governed by the real Gatekeeper V2 and the effect executes with a sealed receipt. Supporting evidence such as Cotal, Tenki, and AIsa×Mitosis resolves progressively **after** the verdict and may remain PENDING without touching the sealed verdict.
3. Click **RUN DENIED PATH**. The same pipeline uses a boundary-restricted URL. If the mounted policy denies or holds it, that result is sealed with a receipt under the same evidence discipline as a permit. The UI does not invent a denial if the selected URL is permitted.

Every chip and card on the page flips only on **runtime evidence from the current run**. Nothing is hardcoded LIVE.

## Architecture and sponsor roles

```
external agents / tools
        |
   Cotal            — identity, authenticated channels, work handoff (never authority)
        |
   AIsa.ONE         — capability layer: real API/model/data invocation (evidence only)
        |
   Mitosis          — packaging/exposure: capability output written as non-authoritative evidence
        |
   Tenki            — external compute: /derive produces derived_claim_only evidence
        |
   Gatekeeper V2    — the ONLY authority: pre-execution verdict, capability-scoped effect
        |
   Cloudflare       — public edge when the quick tunnel is actually running
        |
   sealed receipt   — hash-chained artifact, replayable, idempotency-enforced
```

Structural invariants, enforced in code and demonstrated by the verified core path:

- **Content is evidence, never authority.** Artifact possession, handoff, and every sponsor/compute response are recursively checked; any payload asserting `authority`, `permit`, `capability`, `token`, or `gatekeeper_verdict` is rejected as failed evidence.
- **Pre-execution verdict.** The Gatekeeper decision resolves before any effect; the progressive evidence phase runs after and cannot alter it.
- **Current-run binding.** Tenki claims and AIsa×Mitosis claims must match the exact current ArtifactRef, SHA-256, effect, and principal. Historical claims are never replayed against a fresh artifact.
- **Receipts either way.** Permit and deny both use the same sealed receipt discipline. Replaying an idempotency key returns the exact same sealed artifact (HTTP 409).
- **Failure isolation.** A sponsor or compute plane failing never erases a Gatekeeper verdict or fakes a LIVE state.

## Truth-in-status

`HACKATHON_CHECKPOINT.md` is the authoritative status record, and the Arena chips are driven by per-run responses. At submission time, anything marked PENDING there remains visibly PENDING until its own real end-to-end proof succeeds. The Deterministic Steward is a settled design and is intentionally reported as **IMPLEMENTATION PENDING**. It is not part of the live demo path.

Tenki itself has a historical LIVE VERIFIED worker proof from snapshot `07fd77b8-7caf-400e-8e8e-42eb16396098` and session `01a043be-5240-7bb3-a336-df794b64e56c`. The repository now binds a fresh demo run to Tenki by sending that run's exact `artifact_ref`, matching `artifact_sha256`, current `requested_effect`, and current principal, then validating those same fields on the returned non-authoritative claim. A fresh live local verification of that per-run binding remains PENDING until a template-started worker endpoint is reachable.

## Run it

```powershell
# full local stack: artifact boundary, action edge, orchestrator, nginx public edge
.\scripts\start_day2.ps1 -Restart -GenerateDemoKeys

# optional real Cloudflare edge in front of the public edge; becomes LIVE only with cf-ray evidence
.\scripts\start_cloudflare_edge.ps1

# Tenki: use the published gatekeeper-goi-worker-v2 template image so its baked start_cmd
# launches /home/tenki/gatekeeper-tenki/worker.py automatically. Do not use snapshot+exec.
$env:TENKI_IMAGE_REF = '<published-template-image-ref>'
.\scripts\launch_tenki_swarm.ps1 -Width 2 -ImageRef $env:TENKI_IMAGE_REF

# sponsor planes become LIVE only with real credentials and successful round trips:
#   AIsa:    AISA_API_BASE + AISA_API_KEY (+ AISA_MODEL)   |  or AISA_API_KEY for the Exa adapter
#   Mitosis: MITOSIS_API_KEY (MCP write)                    |  or MITOSIS_OFFICE_ID + authenticated `mi` CLI
```

If no Tenki image has been published yet, leave Tenki fresh-binding status PENDING rather than falling back to the snapshot-plus-`exec` path. The historical Tenki worker proof remains valid historical evidence but must never be replayed as the claim for a new ArtifactRef.

Verification coverage under `src/demo-orchestrator/` includes evidence-pipeline isolation, Tenki current-run claim binding and non-authority enforcement, and both AIsa×Mitosis adapters' authority boundaries. CI is intentionally conserved for final integration confidence rather than used for no-op status updates.

## Repository boundary

This repository is the agent-facing integration and demo shell only. The Gatekeeper V2 authority core (`Gatekeeper-V2-NPU`, pinned by commit in `config/v2-source-pin.json`), policy corpus, and Steward internals are private and are reached through a controlled API surface. The Apache-2.0 license here covers only this repository's contents.
