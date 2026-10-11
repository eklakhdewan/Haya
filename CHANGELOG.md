# Changelog

## Unreleased — documentation and audit refresh (2026-10-11)

### Added
- Post-merge repository audit with source evidence, CI links, severity-ranked findings and remediation order.

### Updated
- README to reflect the audited main SHA, current CI evidence, actual architecture boundaries and production-readiness limitations.
- Start guide to use current manifests and prioritize sandbox safety, durable memory, authorization and staging validation.
- v1 release checklist to remove stale PR/branch/static-analysis status and track remaining P0/P1/P2 gates.
- Phase 1 security report to distinguish implemented controls and passing CI from unverified production/provider work.

### Important status
- PR #7 is merged and the configured CI workflows passed on main commit `a3fc5bd01bd4541cbeb07f6c58081760cc53773e`.
- Haya is **not production-ready** until sandbox selection, durable semantic memory, route/WebSocket authorization, rate/resource controls and deployment recovery gates have evidence.

## [1.0.0] — 2026-09-21

### Rebuilt
- complete product brief
- detailed PRD
- explicit service ownership
- provider abstraction
- memory model
- device security model
- evaluation gates
- 16-week implementation plan
- acquisition strategy
- repository structure
- ready-to-run dependency manifests
- environment template
- JSON schemas
- local infrastructure definition

### Corrected
- removed the assumption that custom Rust WebRTC is mandatory for v1
- separated WebRTC transport events from REST API contracts
- replaced unrestricted LLM-generated Cypher with typed graph operations
- made device actions policy-controlled
- made latency targets measurable rather than guaranteed
- made provider selection replaceable

## [0.1.0] — 2026-09-21

Initial Hina documentation baseline.
