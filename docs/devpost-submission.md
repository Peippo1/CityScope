# CityScope Devpost submission draft

This document is portfolio and submission copy. Review it against the final demo before pasting it into Devpost.

## Project details

**Name:** CityScope

**Tagline:** Evidence-grounded bike-share intelligence for comparing cities without inventing equivalence.

**Recommended category:** Taskmaster

**Hosted project:** https://cityscope-506222.web.app

**Repository:** https://github.com/Peippo1/CityScope

**Architecture:** https://www.figma.com/board/qfv9Yo1Z88fcn7FBArJeTG

## Portfolio summary

CityScope is an agentic geospatial intelligence application that turns a mobility question into a bounded, visual investigation. Its historical cohort covers London, New York City, Chicago, and Washington, DC through matched May 2026 trip data and normalized comparison metrics. A separate City Live Data MCP supplies current Citi Bike, Divvy, Capital Bikeshare, and Vélib' station availability, visibly excluded from historical rankings. Gemini 3.5 Flash selects guarded tools; deterministic City Data MCP queries H3-indexed aggregates; Google Maps supplies current place context; and Google Routes computes attributed bicycle routes.

## Inspiration

City data analysis is still fragmented across downloads, notebooks, dashboards, map searches, and route planners. We wanted to test whether an agent could carry out that multi-step investigation while remaining explicit about observation periods, source provenance, tool use, and uncertainty.

## What it does

- Compares four May 2026 bike-share systems by normalized demand, duration, peak-hour, weekend, and hotspot-concentration metrics rather than raw volume.
- Maps current station availability for NYC, Chicago, Washington, DC, and Paris with provider freshness and an explicit non-comparability boundary.
- Ranks and compares H3-indexed cycling activity using deterministic DuckDB queries.
- Enriches trusted areas with current Google Maps place context.
- Resolves named endpoints and computes Google bicycle routes through bounded activity-informed waypoints.
- Renders map layers, interactive charts, route metrics, source-separated evidence, limitations, and request traces.
- Authenticates users with Google and saves user-owned investigations through a Firebase-token-verified API.

## How we built it

The Next.js frontend is statically exported to Firebase Hosting. A FastAPI service on Cloud Run is the public trust boundary. Gemini 3.5 Flash is accessed through the Google GenAI SDK and returns typed planning decisions. Historical analytics and live GBFS status are isolated in two IAM-protected MCP services. DuckDB queries versioned Parquet artifacts created by four validated source adapters and a shared canonical H3 pipeline. Google Maps resolves current place context and route endpoints; Google Routes returns bicycle route geometry. Firebase Authentication and Firestore provide identity and user-owned persistence. Secret Manager stores server-only credentials.

## Challenges

- Keeping model reasoning separate from deterministic geospatial computation.
- Preserving provenance across four historical providers, four live networks, and current Google context.
- Applying policy checks before planning, before provider calls, and before response delivery.
- Configuring Cloud Run service identity, ingress, MCP DNS-rebinding protection, CORS, and Firebase Hosting safely.
- Designing a data-dense visual workspace that remains usable and accessible on mobile.

## Accomplishments

- Deployed the complete web, API, MCP, authentication, and persistence topology on Google Cloud and Firebase.
- Built an IAM-protected service-to-service MCP boundary.
- Added deterministic agent evaluations, provider fakes, dependency audits, and browser accessibility tests to CI.
- Produced a real Kings Cross-to-Borough bicycle route with historically active waypoint rationale.
- Kept historical, current-place, and route evidence visibly separate throughout the product.
- Added clickable normalized comparisons, city drill-down, live station maps, and judge-visible production/fixture status.

## What we learned

Useful agent autonomy comes from strong contracts. Typed decisions, bounded tool sequences, deterministic calculations, and visible evidence made the system more capable and easier to trust. We also learned that production details such as IAM, CORS, deployment artifacts, and error recovery are part of agent quality, not separate from it.

## What's next

- Add explicit route fields and richer temporal filters.
- Promote a new common historical month only after all four providers pass the same validation gates.
- Expand the Paris archive pilot into source-specific trend products after enough observations exist.
- Expand saved investigation history and shareable visual reports.
- Add multi-turn clarification and asynchronous investigation workflows.
- Extend the data foundation to more modes and cities without weakening provenance.

## Built with

Gemini 3.5 Flash, Google GenAI SDK, Google Cloud Run, Firebase Hosting, Firebase Authentication, Firestore, Secret Manager, Artifact Registry, Google Maps JavaScript API, Google Maps Grounding, Google Routes API, FastAPI, MCP, Next.js, React, DuckDB, Parquet, H3, Python, and TypeScript.

## Submission checklist

- [x] Hosted project URL
- [x] Repository with local spin-up instructions
- [x] Architecture diagram
- [x] Features, technologies, data sources, findings, and learnings copy
- [x] Public Google Cloud deployment evidence available for the demo
- [ ] Record and publish the approximately four-minute demo video
- [ ] Share the private repository with `testing@devpost.com` and `cloudhackathons@google.com`, or make it public before judging
- [ ] Publish the build article on a public platform and retain the hackathon-purpose disclosure
- [ ] Add the final video and public article URLs to this document and Devpost
- [ ] Complete the Devpost project form and submit before the deadline
