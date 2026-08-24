# CityScope privacy notice (POC)

CityScope is a judge-facing London cycling investigation demo. Historical TfL activity is displayed as a May 2026 snapshot and is not live cycling behaviour.

When Google sign-in and saved investigations are enabled, CityScope stores the signed-in Firebase user identifier, the submitted question, selected H3 areas, investigation status, a concise response summary, historical TfL evidence metadata, and the dataset snapshot identifier. Users can delete their own saved investigations.

CityScope does not store Firebase ID tokens, API keys, request headers, raw Google Maps Grounding place payloads, or Google route geometry. Current Maps context and route results are generated for the active request and should be treated as temporary.

Provider credentials are server-only. Browser-visible Firebase and Maps configuration values are restricted public identifiers, not secrets.
