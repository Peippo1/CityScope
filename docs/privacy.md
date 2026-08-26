# CityScope privacy notice (POC)

CityScope is a judge-facing bike-share intelligence demo. Historical London, NYC, Chicago, and Washington, DC activity is displayed as a matched May 2026 snapshot and is not live cycling behaviour. Paris Vélib' station status is current operational data and is not used for historical city comparisons.

When Google sign-in and saved investigations are enabled, CityScope stores the signed-in Firebase user identifier, the submitted question, selected H3 areas, investigation status, a concise response summary, historical TfL evidence metadata, and the dataset snapshot identifier. Users can delete their own saved investigations.

CityScope does not store Firebase ID tokens, API keys, request headers, raw Google Maps Grounding place payloads, or Google route geometry. Current Maps context and route results are generated for the active request and should be treated as temporary.

The private Paris archive stores hourly compressed station-level bike and dock availability from the official Vélib' feeds. It contains no rider identity or trip history, is not browser-readable, and is not used for trend claims until a meaningful observation history exists.

Provider credentials are server-only. Browser-visible Firebase and Maps configuration values are restricted public identifiers, not secrets.
