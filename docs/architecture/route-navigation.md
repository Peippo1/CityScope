# CityScope route-navigation architecture

## Request lifecycle

```text
Next.js CityScopeWorkspace
  └─ InvestigationRequest(question + typed route context)
      └─ FastAPI /investigate
          └─ InvestigationService
              ├─ Gemini/ADK: intent and preference extraction only
              ├─ GuardrailPolicy: scope, budgets, and endpoint safety
              ├─ Location resolver: named search or user-selected coordinates
              ├─ City Data MCP: optional historical corridor context
              ├─ Place discovery: planned stops and optional facilities
              ├─ JourneyPlanner + Google Routes API: deterministic geometry
              └─ Route validation → InvestigationResult → map/result UI
```

Gemini does not receive or construct coordinates, Place IDs, or Routes payloads. The backend owns provider calls and validates the returned endpoint geography. Planned stops become route waypoints; facilities remain optional nearby results and do not change geometry.

## Root cause of the starting-location regression

The UI already collected `start_location`, but the backend passed route endpoint authority to Gemini's `route.intent` decision. When Gemini returned the bounded fallback pair `City centre` → `a nearby park`, the deterministic route layer trusted that decision and discarded the structured UI value. The frontend also previously captured stale control values in its submit callback; that closure issue was fixed in `cb3d1c4`, but production verification showed the backend still needed an authority boundary.

## Current route state

`InvestigationContext` is the request-scoped route state. It now carries activity, origin mode, named or selected origin data, optional destination data, journey type, requested distance, planned stops, facilities, preferences, and conversation turns. Current-location coordinates are used for the request only; they are not persisted in saved investigations.

Deterministic rules:

1. User-selected origin coordinates take precedence over Gemini output.
2. A named origin or destination supplied in structured context takes precedence over inferred endpoints.
3. Explicit `from … to …` text can recover a destination only when the model returned a generic endpoint.
4. Generic endpoints are rejected rather than silently substituted.
5. Approximate-distance requests without a destination or implemented loop planner return a clear limitation; the system does not claim exact distance optimisation.

## Components reused and changed

- Reused `InvestigationService`, `GoogleMapsGroundingClient`, `GoogleRoutesService`, `JourneyPlanner`, MCP clients, existing budgets, and policy checks.
- Extended the typed request context for route state and current-location/selected-place input.
- Added deterministic selected-location resolution and endpoint authority checks.
- Added current-location and destination controls to the existing composer.
- Kept Gemini as a lean intent coordinator rather than introducing additional agents.

## Known limitations

- Approximate-distance loop optimisation is not implemented; distance requests require a resolvable destination for now.
- A selected place currently needs coordinates from the trusted UI selection; raw Place IDs without coordinates are rejected rather than geocoded by an LLM.
- Running uses Google walking geometry as the existing safe approximation.
