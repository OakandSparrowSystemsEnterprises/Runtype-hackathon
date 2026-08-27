# Gatekeeper V2 — Agent-Native Universal Artifact Authority

**Agent Native Builders Hackathon @ Cloudflare HQ · August 26–27, 2026 · Oak & Sparrow Systems Enterprise**

> **Work can move between agents. Authority does not move with it.**

Agents exchange artifacts, coordinate over messaging fabrics, and fan work out to swarm compute — but no content, credential possession, coordination message, or compute result ever grants the authority to act. Every consequential effect is resolved by Gatekeeper V2 **before execution** and leaves a sealed, hash-chained, replayable receipt. Denials get the same receipts as permits.

## The 60-second judge path

1. Open the Day 2 Arena (public edge `/`, served by nginx — through the Cloudflare tunnel URL when the Cloudflare edge script is running).
2. Click **RUN DAY 2 DEMO** — one live run: fresh bytes become an immutable SHA-256 ArtifactRef; Agent A is authenticated and **denied (HTTP 403, no capability)**; the same artifact is handed to Agent B with `authority_transfer_from_artifact=false`; Agent B is independently governed by the real Gatekeeper V2 and the effect executes with a sealed receipt. Supporting evidence (Cotal, five-domain estate, Tenki, AIsa×Mitosis) then resolves progressively **after** the verdict — it can fail without ever touching the sealed verdict.
3. Click **RUN DENIED PATH** — the same pipeline with a boundary-restricted URL: Gatekeeper returns a deny/hold, and the denial is sealed with a receipt under the same evidence discipline as a permit.

Every chip and card on the page flips only on **runtime evidence from the current run** — nothing is hardcoded live.

## Architecture and sponsor roles

```
external agents / tools
        |
   Cotal            — identity, authenticated channels, work handoff (never authority)
        |
   AIsa.ONE         — capability layer: real API/model/data invocation (evidence only)
        |
   Mitosis          — packaging/exposure: capability output written into a Cortex memory graph
        |
   Tenki            — swarm compute: deterministic replica /derive claims (derived_claim_only)
        |
   Gatekeeper V2    — the ONLY authority: pre-execution verdict, capability-scoped effect
        |
   Cloudflare       — public edge in front of the nginx service path
        |
   sealed receipt   — hash-chained artifact, replayable, idempotency-enforced
```

Structural invariants, enforced in code and demonstrated live:

- **Content is evidence, never authority.** Artifact possession, handoff, and every sponsor/compute response are recursively checked; any payload asserting `authority`, `permit`, `capability`, `token`, or `gatekeeper_verdict` is rejected as failed evidence.
- **Pre-execution verdict.** The Gatekeeper decision resolves before any effect; the progressive evidence phase runs after and cannot alter it.
- **Current-run binding.** Tenki claims and AIsa×Mitosis claims must match the exact current ArtifactRef, SHA-256, effect, and principal — historical claims are never replayed.
- **Receipts either way.** Permit and deny both produce sealed, chain-verified artifacts; replaying an idempotency key returns the exact same sealed artifact (HTTP 409).
- **Failure isolation.** A sponsor or compute plane failing never erases a Gatekeeper verdict or fakes a LIVE state.

## Truth-in-status

Live state is recorded, not asserted: `HACKATHON_CHECKPOINT.md` is the authoritative status record, and the Arena's chips are driven by per-run responses. At submission time, statuses follow that record — anything marked PENDING there is truthfully pending (e.g., a sponsor plane whose credentials are not configured in the demo shell shows PENDING, never a fake pass). The Deterministic Steward design is intentionally reported as implementation-pending rather than demo-inflated.

## Run it

```powershell
# full local stack: artifact boundary, action edge, orchestrator, nginx public edge
.\scripts\start_day2.ps1 -Restart -GenerateDemoKeys

# real Cloudflare edge in front of the public edge (quick tunnel; prints the public URL)
.\scripts\start_cloudflare_edge.ps1

# Tenki replica swarm (template-native startup), then rerun the demo in the same shell
.\scripts\launch_tenki_swarm.ps1 -Width 2

# sponsor planes go LIVE only with real credentials in the shell:
#   AIsa:    AISA_API_BASE + AISA_API_KEY (+ AISA_MODEL)   |  or AISA_API_KEY for the Exa adapter
#   Mitosis: MITOSIS_API_KEY (MCP write)                    |  or MITOSIS_OFFICE_ID + authenticated `mi` CLI
```

Verification: `python -m unittest` over `src/demo-orchestrator/` covers the evidence pipeline isolation contract, Tenki claim binding and consensus, and both AIsa×Mitosis adapters' authority boundaries. CI is intentionally skipped to conserve GitHub Actions usage; suites run locally.

## Repository boundary

This repository is the agent-facing integration and demo shell only. The Gatekeeper V2 authority core (`Gatekeeper-V2-NPU`, pinned by commit in `config/v2-source-pin.json`), policy corpus, and Steward internals are private and are reached through a controlled API surface. The Apache-2.0 license here covers only this repository's contents.
