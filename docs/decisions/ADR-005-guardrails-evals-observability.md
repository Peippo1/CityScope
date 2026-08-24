# ADR-005: Guardrails, deterministic evaluations, and optional telemetry export

## Status

Accepted.

## Decision

CityScope centralizes deterministic investigation policy in the API layer. The policy owns scope rejection, trusted-H3 checks, model/tool/provider budgets, route-intent constraints, waypoint bounds, safe provider failures, and final-response safety checks.

A versioned, fake-adapter golden suite is the authoritative CI gate. Paid model calls, live provider calls, and LLM-as-judge scoring are excluded from CI.

Observability uses a small internal metadata-only interface. Local structured JSON is the default. LangSmith is an optional adapter with a lazy SDK dependency, zero sampling by default, no LangChain dependency, and fail-open export behavior.

## Rationale

Deterministic policy and evaluation provide reproducible safety and regression checks without adding provider cost. A vendor-neutral telemetry boundary prevents tracing from changing core orchestration or becoming an availability dependency. The restricted event schema makes accidental prompt, credential, place-result, or route-geometry export structurally difficult.

## Consequences

- Policy reason codes are stable public trace metadata; human-readable wording may evolve.
- Attempted/rejected tools appear in traces, while provider call counts record only actual external execution.
- LangSmith must be explicitly installed and configured before any export can occur.
- Online evaluators and production trace export require a separate approval and privacy review.
