# Building CityScope: an AI guide for memorable city routes

**CityScope turns one travel question into a grounded run or ride: a real route, a handful of interesting places, and somewhere good to stop.**

> I created this article for the purpose of entering CityScope in the All Things Agentic Hackathon.

[Try CityScope](https://cityscope-506222.web.app) · [Read the public article](https://tfinch.dev/writing/building-cityscope) · [View the repository](https://github.com/Peippo1/CityScope) · [All Things Agentic Hackathon](https://allthingsagentichackathon.devpost.com/)

## The moment CityScope is built for

You have two free hours in a city you barely know. You want a 10 km run through parks and landmarks, or a scenic bike ride with coffee at the end. Finding a route, checking its distance, researching the neighbourhood and choosing a worthwhile stop normally means juggling several apps. CityScope makes that a single request.

The result is deliberately simple: an approximate route that fits the request, shown prominently on the map; two to four named places worth seeing; an appropriate food or drink stop when requested; and links that take the plan into Google Maps.

## An agent with useful boundaries

Google ADK provides the agent runtime and a root `LlmAgent` powered by Gemini 3.5 Flash. Gemini interprets the city, activity, rough duration or distance and the character of the outing. It can choose from a constrained vocabulary, but it never invents coordinates or route geometry.

After that planning decision, deterministic backend code takes over. It matches a curated route concept for the city, resolves named locations and nearby stops through Google Maps Grounding, validates every result against city bounds, and asks Google Routes for actual WALK or BICYCLE geometry. Running uses walking geometry and is described honestly as an approximation.

```text
Traveller's request
  -> Gemini + Google ADK
  -> curated city route concept
  -> Google Maps Grounding + optional City Data MCP context
  -> validated waypoints + Google Routes
  -> interactive map, stops and shareable plan
```

## Grounding matters more than fluency

A confident fictional café is worse than no recommendation. CityScope keeps provider identifiers and Maps links, never fabricates ratings, caps place searches and route calls, and rejects model-supplied coordinates or raw provider payloads. Historical mobility evidence remains available as supporting intelligence, but it cannot block the route-template and Maps path that makes the public experience reliable.

## What changed during the hackathon

The project began as an urban analytics workspace. User testing exposed a clearer, more human job: help someone enjoy a city. That insight changed the hierarchy without discarding the engineering underneath. H3 analytics, City Data MCP, provenance and execution traces still strengthen the agent, but the traveller now sees the product first: city, run or cycle, request, map, stops and share actions.

## What I learned

The best agent experience was not the one with the most visible agent machinery. It was the one where the model handled interpretation, deterministic services handled facts and geometry, and the interface made the outcome immediate. Strong schemas, small call budgets, friendly failure states and honest approximations made the demo both more useful and more trustworthy.

CityScope is a working hackathon prototype. Try a London or New York route, then inspect the repository for the ADK agent, guardrails, route templates and Google Cloud deployment.
