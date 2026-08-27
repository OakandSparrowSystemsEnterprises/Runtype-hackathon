# Gatekeeper V2 — Agent-Native Universal Artifact Authority

Hackathon integration repository for the Agent Native Builders Hackathon at Cloudflare HQ, August 26–27, 2026.

**Judges: start with [SUBMISSION.md](SUBMISSION.md)** — the 60-second demo path, sponsor architecture, and truthful live-status record. Day 2 live state is tracked in [HACKATHON_CHECKPOINT.md](HACKATHON_CHECKPOINT.md); the Day 2 Arena (`web/day2-arena.html`, served at the public edge `/`) proves permit **and** denied paths live, with every status chip driven by current-run runtime evidence.

## What this repository is

This repository contains the agent-facing integration layer built around Gatekeeper V2 for the hackathon. It is intentionally separated from the proprietary Gatekeeper V2 core.

The goal is to let external agent fleets:

- discover Gatekeeper as a machine-readable service;
- authenticate as bounded machine principals;
- submit arbitrary artifacts as raw bytes;
- receive immutable content-addressed artifact references;
- hand work between agents without transferring authority through content;
- propose governed effects;
- receive deterministic permit, hold, deny, or abstain outcomes with replayable receipts.

The core product principle is:

> Content can provide evidence. Content cannot grant authority.

## Architecture

```text
External agent fleet
        |
        v
Agent-native edge
(discovery + authentication)
        |
        v
Universal Artifact Boundary
(raw bytes -> digest -> provenance)
        |
        v
Immutable ArtifactRef
        |
        v
Private Gatekeeper V2 API
        |
        v
Gate 1 -> bounded worker -> exact-result Gate 2
        |
        v
Controlled effect + sealed receipt
```

Gatekeeper V2 remains the deterministic authority layer. This repository provides the external discovery, artifact, interoperability, demo, and test surfaces needed for agent-native use.

## Initial build targets

1. Machine-readable discovery at `/.well-known/ai-agent.json`.
2. Universal Artifact Boundary that hashes and identifies original bytes before interpretation.
3. Immutable artifact references with provenance and parent/child lineage.
4. External-agent identity binding that cannot be self-asserted from payload content.
5. A Gatekeeper client that calls the private hosted V2 service.
6. A live multi-agent handoff using Cotal or the event platform.
7. One permitted governed effect and one denied unauthorized effect.
8. Replay and receipt verification.

## Repository boundary

This repository does **not** contain the Gatekeeper V2 authority implementation, policy engine, proprietary policy corpus, Steward internals, customer materials, signing secrets, or other protected OASSE source code.

The hackathon integration communicates with Gatekeeper V2 through a controlled API surface.

## Proposed structure

```text
.
├── README.md
├── LICENSE
├── .gitignore
├── .well-known/
│   ├── ai-agent.json
│   └── agent-card.json
├── src/
│   ├── artifact-boundary/
│   ├── discovery/
│   ├── gatekeeper-client/
│   └── integrations/
│       └── cotal/
├── tests/
│   ├── artifacts/
│   ├── authority/
│   └── adversarial/
├── fixtures/
└── demo/
```

## Security invariants

- Govern the bytes before governing meaning.
- Preserve the original artifact. Transformations create children, never replacements.
- Declared MIME type, detected type, and parsed type are separate claims.
- Unsupported content remains governed and may fail closed when evidence is insufficient.
- External content cannot create, widen, or impersonate authority.
- Delegation cannot exceed the delegator's scope.
- Replayed operations must not produce duplicate effects.
- The private Gatekeeper V2 repository is not required for event-agent access.

## License boundary

The Apache License 2.0 in this repository applies only to the contents of `Runtype-hackathon` that are distributed under that license. It does not grant a license to Gatekeeper V2, Oak & Sparrow Systems Enterprise proprietary source code, policy corpora, customer materials, trade secrets, or other software and intellectual property not contained in this repository, except to the extent any rights are expressly granted by a separate written license.

## Organization

Oak & Sparrow Systems Enterprise
