export const metadata = {
  title: "Building CityScope · An AI guide for memorable city routes",
  description: "How CityScope uses Google ADK, Gemini, Maps Grounding and Google Routes to plan runs and rides through a new city.",
};

export default function CityScopeBuildStory() {
  return <main id="main-content" className="blog-page">
    <nav className="blog-nav" aria-label="Article navigation"><a className="brand" href="/"><span>← CityScope</span></a><a href="https://github.com/Peippo1/CityScope">View the code</a></nav>
    <article>
      <p className="eyebrow">Build story · All Things Agentic Hackathon</p>
      <h1>Building an AI guide for memorable city routes</h1>
      <p className="blog-lede">CityScope turns one travel question into a grounded run or ride: a real route, a handful of interesting places, and somewhere good to stop.</p>
      <p className="blog-disclosure">I created this article for the purpose of entering CityScope in the All Things Agentic Hackathon.</p>
      <div className="blog-actions"><a className="primary-link-button" href="/">Try CityScope</a><a href="https://allthingsagentichackathon.devpost.com/">Visit the hackathon</a></div>

      <h2>The moment CityScope is built for</h2>
      <p>You have two free hours in a city you barely know. You want a 10 km run through parks and landmarks, or a scenic bike ride with coffee at the end. Finding a route, checking its distance, researching the neighbourhood and choosing a worthwhile stop normally means juggling several apps. CityScope makes that a single request.</p>

      <blockquote>“I’ve just arrived in London. Give me a scenic hour-long ride from King’s Cross and find me a good coffee stop.”</blockquote>

      <p>The result is deliberately simple: a route that fits the request approximately, shown prominently on the map; two to four named places worth seeing; an appropriate food or drink stop when requested; and links that take the plan into Google Maps.</p>

      <h2>An agent with useful boundaries</h2>
      <p>Google ADK provides the agent runtime and a root <code>LlmAgent</code> powered by Gemini 3.5 Flash. Gemini interprets the city, activity, rough duration or distance and the character of the outing. It can choose from a constrained vocabulary—scenic, parks, landmarks, coffee or food—but it never invents coordinates or route geometry.</p>
      <p>After that planning decision, deterministic backend code takes over. It matches a curated route concept for the city, resolves named locations and nearby stops through Google Maps Grounding, validates every result against city bounds, and asks Google Routes for the actual WALK or BICYCLE geometry. Running uses walking geometry and is described honestly as an approximation.</p>

      <pre aria-label="CityScope planning flow">{`Traveller's request
  ↓
Gemini + Google ADK
  ↓
Curated city route concept
  ↓
Google Maps Grounding + optional City Data MCP context
  ↓
Validated waypoints + Google Routes
  ↓
Interactive map, stops and shareable plan`}</pre>

      <h2>Grounding matters more than fluency</h2>
      <p>A confident fictional café is worse than no recommendation. CityScope keeps provider identifiers and Maps links, never fabricates ratings, caps place searches and route calls, and rejects model-supplied coordinates or raw provider payloads. Historical mobility evidence remains available as supporting intelligence, but it cannot block the route-template and Maps path that makes the public experience reliable.</p>

      <h2>What changed during the hackathon</h2>
      <p>The project began as an urban analytics workspace. User testing exposed a clearer, more human job: help someone enjoy a city. That insight changed the hierarchy without discarding the engineering underneath. H3 analytics, City Data MCP, provenance and execution traces still strengthen the agent, but the traveller now sees the product first: city, run or cycle, request, map, stops and share actions.</p>

      <h2>What I learned</h2>
      <p>The best agent experience was not the one with the most visible agent machinery. It was the one where the model handled interpretation, deterministic services handled facts and geometry, and the interface made the outcome immediate. Strong schemas, small call budgets, friendly failure states and honest approximations made the demo both more useful and more trustworthy.</p>

      <p className="blog-closing"><strong>CityScope is a working hackathon prototype.</strong> Try a London or New York route, then inspect the <a href="https://github.com/Peippo1/CityScope">repository</a> for the ADK agent, guardrails, route templates and Google Cloud deployment.</p>
    </article>
  </main>;
}
