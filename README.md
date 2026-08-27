# Gatekeeper V2 — Agent-Native Universal Artifact Authority

Hackathon integration repository for the Agent Native Builders Hackathon at Cloudflare HQ, August 26–27, 2026.

> **Work can move between agents. Authority does not move with it.**

Gatekeeper V2 is the sole pre-execution authority layer in this demo. Agents, coordination fabrics, sponsor systems, models, compute workers, and artifact contents may provide work or evidence, but none of them can create or transfer authority.

## Final hackathon demo

**Judges: start with [SUBMISSION.md](SUBMISSION.md)** for the 60-second path and full architecture notes.

Live Arena:

- local: `http://127.0.0.1:8080/day2-arena.html`
- submitted public demo: `https://chess-guidelines-sky-tuesday.trycloudflare.com`

Click **RUN LIVE GOVERNANCE ARENA**. A fresh run demonstrates:

1. Raw bytes enter the Universal Artifact Boundary and become an immutable SHA-256 `ArtifactRef`.
2. **Agent A is authenticated and denied (HTTP 403).**
3. The exact same artifact is handed off.
4. `authority_transfer_from_artifact` remains **false**.
5. **Agent B must independently satisfy Gatekeeper** and receives the governed effect only after its own authority evaluation.
6. Gatekeeper seals the receipt before the slower supporting systems finish.
7. Supporting coordination, evidence, compute, replay, and verification continue afterward and cannot retroactively change the sealed verdict.

The central proof is visible in the UI:

> **THE ARTIFACT MOVED. AUTHORITY DID NOT.**

## Final verified runtime state

The final integrated Arena run reached the following truthful state:

| Plane / proof | Final state | Authority |
| --- | --- | --- |
| Gatekeeper V2 | **SEALED** | **sole authority** |
| Agent A execution | **DENIED** | no transferred authority |
| Agent B governed effect | **independently authorized** | Gatekeeper-resolved |
| Universal Artifact Boundary | **LIVE** | none |
| Cotal coordination | **LIVE** | none |
| Deterministic Steward | **PARTIAL** | none |
| AIsa.ONE → Mitosis Cortex | **LIVE** | none |
| Tenki current-run compute | **PENDING** | none |
| Five-domain governed estate | **5/5 GOVERNED** | Gatekeeper-resolved effects |
| Receipt-chain verification | **VERIFIED** | verification only |
| Replay / idempotency | **SAME ARTIFACT** | no duplicate authority/effect |

The Steward is implemented under `oasse.deterministic-steward.v2`; its final status is **PARTIAL** because the Tenki current-run workers did not have reachable `/derive` endpoints. That does not affect the already-sealed Gatekeeper verdict.

AIsa.ONE and Mitosis are integrated through the proven sponsor-evidence route: a real AIsa.ONE Exa result is hashed and written into Mitosis Cortex as non-authoritative evidence with `authority=false`. The final Arena run showed this plane **LIVE**.

Tenki remains **PENDING** for fresh current-run binding. Historical Tenki worker evidence is retained as historical evidence only and is never replayed as proof for a new `ArtifactRef`.

## Measured performance shown in the Arena

The Arena reports current-run authority timing dynamically rather than hard-coding a demo result. It also displays the existing direct Parent Shield governance benchmark:

- **22.70 ms p50**
- **24.65 ms mean**
- **36.45 ms p95**
- **48.29 ms max**

A separate saturation run measured **893 req/s** at 80-way concurrency on a 4-core Linux VM. That saturation figure is explicitly labeled **MEASURED — NOT SEALED/CERTIFIED**.

## Architecture

```text
External agents / tools
        |
        v
Agent-native edge
(discovery + bounded machine identity)
        |
        v
Universal Artifact Boundary
(raw bytes -> digest -> provenance)
        |
        v
Immutable ArtifactRef
        |
        +------------------------------+
        |                              |
        v                              v
   Cotal / Steward              AIsa.ONE / Mitosis / Tenki
 coordination + handoff          supporting evidence / compute
   authority = false                 authority = false
        |                              |
        +---------------+--------------+
                        |
                        v
                 Gatekeeper V2
              SOLE AUTHORITY SOURCE
              pre-execution verdict
                        |
                        v
              controlled effect +
              sealed replayable receipt
```

Supporting systems may finish later, fail, or remain pending. They cannot grant authority and cannot alter a sealed Gatekeeper verdict.

## What this repository contains

This repository is the agent-facing integration and demo shell around Gatekeeper V2. It intentionally excludes the proprietary Gatekeeper V2 authority core.

It provides surfaces for external agent fleets to:

- discover Gatekeeper through machine-readable metadata;
- authenticate as bounded machine principals;
- submit arbitrary artifacts as raw bytes;
- receive immutable content-addressed artifact references;
- preserve provenance and parent/child lineage;
- hand work between agents without transferring authority through content;
- propose governed effects;
- receive deterministic authority outcomes;
- verify sealed receipts and idempotent replay;
- attach non-authoritative sponsor and compute evidence after the authority decision.

## Security invariants

- **Govern bytes before meaning.**
- Preserve the original artifact; transformations create children, never replacements.
- Content can provide evidence. **Content cannot grant authority.**
- Artifact possession or handoff cannot transfer execution authority.
- External content cannot create, widen, or impersonate authority.
- Delegation cannot exceed the delegator's scope.
- Sponsor, model, compute, and coordination outputs are non-authoritative.
- Supporting evidence runs after the Gatekeeper verdict and cannot change it.
- Replayed operations must not produce duplicate effects.
- Permit and deny use the same sealed receipt discipline.
- Failed or unavailable supporting planes never erase or fabricate a Gatekeeper result.

## Run locally

```powershell
$env:GATEKEEPER_V2_SOURCE_ROOT="C:\Users\ankou\Downloads\Gatekeeper-V2-NPU"
.\scripts\start_day2.ps1 -Restart -GenerateDemoKeys
```

Then open:

```text
http://127.0.0.1:8080/day2-arena.html
```

Sponsor planes become `LIVE` only when their real credentials/runtime are present and their round trips succeed. Status chips are driven by current-run evidence; the UI does not fake a sponsor or compute success.

## Repository boundary

This repository does **not** contain the Gatekeeper V2 authority implementation, proprietary policy engine or corpus, Steward internals, customer materials, signing secrets, or other protected Oak & Sparrow Systems Enterprise source code.

The integration reaches the private Gatekeeper V2 source-of-truth through a controlled API surface. The pinned source reference is maintained in `config/v2-source-pin.json`.

## License boundary

The Apache License 2.0 in this repository applies only to the contents of `Runtype-hackathon` distributed under that license. It does not grant a license to Gatekeeper V2, Oak & Sparrow Systems Enterprise proprietary source code, policy corpora, customer materials, trade secrets, or other software and intellectual property not contained in this repository except where rights are expressly granted by separate written license.

## Organization

Oak & Sparrow Systems Enterprise
