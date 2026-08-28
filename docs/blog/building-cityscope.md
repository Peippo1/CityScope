# Building CityScope: an agent that can reason about movement without inventing the city

**CityScope combines Gemini, deterministic geospatial analytics, Google Maps, and Google Cloud to turn cross-city mobility questions into bounded, visual investigations.**

> I created this article for the purpose of entering CityScope in the All Things Agentic Hackathon.

[Try CityScope](https://cityscope-506222.web.app) | [All Things Agentic Hackathon](https://allthingsagentichackathon.devpost.com/)

## The problem

City data is abundant, but answering a practical question still involves too much manual work. A transport planner, local business owner, or curious resident may need to find the right dataset, understand its observation period, translate locations into a spatial index, compare areas, inspect nearby places, and then move the result into a map or route planner.

A normal chatbot can describe that workflow. CityScope is designed to carry it out.

CityScope now compares a matched May 2026 historical cohort: London, New York City, Chicago, and Washington, DC. A user can inspect normalized demand patterns, then drill into one city's H3 hotspots, nearby amenities, or a bicycle route. NYC, Chicago, DC, and Paris optionally expose a separate live mode: fixed official provider feeds show station availability and freshness, but are never ranked beside historical trip demand. London stays historical-only because Santander supply is not representative of the wider cycling market.

## Why a bounded agent

Geospatial answers become misleading quickly when an agent is allowed to improvise. CityScope therefore separates reasoning from computation:

1. Gemini 3.5 Flash classifies the question and selects an allowed operation.
2. A policy boundary validates the request, tool name, arguments, call order, and budget.
3. City Data MCP runs deterministic DuckDB queries over versioned Parquet aggregates.
4. Google Maps context and Google Routes are called only when the investigation requires them.
5. The API validates the structured result before the browser receives it.

The model decides what evidence is needed. It does not calculate journey totals, invent coordinates, generate route geometry, or bypass the tool policy.

## Building the data foundation

Each historical city uses a pinned May 2026 trip snapshot. The ingestion pipeline reads official archives in bounded chunks, interprets timestamps in the source city's local timezone, rejects invalid durations, missing coordinates, duplicate trip IDs, invalid H3 assignments, and out-of-window rows, then writes checksummed Parquet plus reasoned quarantine metadata. The verified cohort contains 4,680,767 accepted Citi Bike trips, 653,075 Divvy trips, 588,599 Capital Bikeshare trips, and 854,872 TfL trips. Cross-city views use per-active-station demand, duration, time-pattern, and unique-trip hotspot concentration rather than raw journey totals.

That snapshot is deliberately labelled as historical throughout the interface. CityScope does not present it as live cycling behaviour. Current place context and bicycle routes are shown as separate Google-backed sources, each with its own attribution and limitations.

This provenance-first approach is less flashy than quietly blending every source together, but it makes the final answer inspectable.

## The agent workflow

A request such as “Plan a bicycle route from Kings Cross to Borough” crosses several boundaries:

```text
Browser
  -> FastAPI policy and orchestration
  -> Gemini structured plan
  -> Google Maps endpoint resolution
  -> City Data MCP hotspot query
  -> deterministic waypoint scoring
  -> Google Routes bicycle route
  -> validated answer, evidence, trace, and map layers
```

The route planner does more than draw a line between two endpoints. It can score historical high-activity cells near the route corridor, select bounded waypoints, request the route from Google, and explain why those waypoints were considered. The UI then renders distance, estimated duration, route warnings, historical evidence, and provider attribution.

## A visual workspace, not another chat window

The latest interface rewrite moves the product away from a chat-first layout. The main screen now combines:

- an interactive Google Map with selectable H3 activity cells;
- a cross-city question composer that exposes the agent's bounded `compare_cities` trace;
- deterministic leader, cohort-range, and closest-pair findings for each approved metric;
- a city-aware live map with current bike and dock availability;
- a colour-coded activity chart linked to map selection;
- a real request-flow view driven by API trace state;
- natural-language investigation and route controls;
- source-separated evidence, limitations, and methodology;
- Google sign-in and user-owned saved investigations.

The colour system takes cues from Google’s product language, but the interface remains an operational dashboard: compact controls, stable map dimensions, visible loading and failure states, keyboard-accessible chart bars, and responsive layouts for desktop and mobile.

## Running on Google Cloud

CityScope is deployed across intentionally separate trust boundaries:

- Firebase Hosting serves the static Next.js application.
- Firebase Authentication provides Google sign-in.
- Firestore stores user-owned saved investigations through the API only.
- A public Cloud Run service hosts FastAPI.
- An IAM-protected Cloud Run service hosts City Data MCP.
- A second IAM-protected service hosts fixed-provider City Live Data MCP.
- Cloud Scheduler runs the private hourly Paris archive pilot.
- Artifact Registry stores the API and MCP images.
- Secret Manager supplies server-only provider credentials.

The browser never receives Gemini, Maps Grounding, Routes, or service-account credentials. Cloud Run service-to-service calls use an identity token, and only the API service account can invoke the MCP service.

To keep the first comparison responsive on a cold Cloud Run instance, the artifact build also produces a small five-metric matrix. It is accepted only when all four snapshot IDs, artifact names, and provenance checksums match the active cohort. If that validation fails, CityScope falls back to the canonical Parquet calculation rather than serving stale values.

## What we learned

The most important engineering lesson was that an agent becomes more useful when its freedom is shaped carefully. Structured planning, deterministic tools, explicit source boundaries, call budgets, and typed outputs made it possible to create a richer experience without making the system harder to trust.

The second lesson was operational: a working demo depends as much on CORS, IAM, DNS-rebinding protection, deployment artifacts, and failure states as it does on the model prompt. The final product is stronger because those constraints are visible in the architecture and covered by tests.

## What comes next

The current release proves the investigation loop. The next iterations will focus on:

- explicit route origin and destination controls alongside natural language;
- additional time filters and comparative visualisations;
- enough archived observations to support carefully bounded Paris availability trends;
- richer saved-investigation history and shareable reports;
- evaluation cases for multi-turn clarification and longer-running investigations;
- a public write-up and four-minute demo for the hackathon submission.

CityScope started with a simple question: can an agent help people explore a city without hiding where its answer came from? The working system suggests that the answer is yes, provided the reasoning remains bounded and the evidence remains visible.
